'use strict';
// The caller supplies its actual Canvas 2D context and registers the final font.
// No raster clipping, horizontal compression, ellipsis or font shrinking.
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');

function requirePositive(value, name) {
  if (!Number.isFinite(value) || value <= 0) throw new Error(`${name} must be positive`);
}
function paddingValues(value = 24) {
  const p = typeof value === 'number' ? {top:value,right:value,bottom:value,left:value} : value;
  for (const key of ['top','right','bottom','left']) {
    if (!Number.isFinite(p[key]) || p[key] < 0) throw new Error(`Invalid padding.${key}`);
  }
  return p;
}
function measure(ctx, text) {
  const m = ctx.measureText(text || '가Ag');
  const ascent = m.actualBoundingBoxAscent, descent = m.actualBoundingBoxDescent;
  if (![ascent,descent,m.actualBoundingBoxLeft,m.actualBoundingBoxRight,m.width].every(Number.isFinite)) {
    throw new Error('Actual glyph metrics are required');
  }
  const left = text ? Math.max(0,m.actualBoundingBoxLeft) : 0;
  const right = text ? Math.max(m.width,m.actualBoundingBoxRight) : 0;
  return {ascent:Math.max(0,ascent),descent:Math.max(0,descent),left,right,width:left+right};
}
function splitWord(ctx, word, width) {
  if (measure(ctx,word).width <= width) return [word];
  if (/https?:\/\/|@|시[·ㆍ]군|^\d[\d.\-():~]+$/.test(word)) {
    throw new Error(`Protected token does not fit; widen or recompose: ${word}`);
  }
  const graphemes = [...new Intl.Segmenter('ko',{granularity:'grapheme'}).segment(word)].map(x=>x.segment);
  const parts=[]; let current='';
  for (const char of graphemes) {
    if (measure(ctx,char).width > width) throw new Error('A glyph cannot fit the text area');
    if (current && measure(ctx,current+char).width > width) {parts.push(current);current=char;}
    else current+=char;
  }
  if (current) parts.push(current);
  return parts;
}
function wrapText(ctx, text, width) {
  const result=[];
  for (const paragraph of text.split('\n')) {
    if (!paragraph.trim()) {result.push('');continue;}
    let line='';
    for (const word of paragraph.trim().split(/\s+/u)) {
      const parts=splitWord(ctx,word,width);
      for (let i=0;i<parts.length;i++) {
        const candidate=line ? line+' '+parts[i] : parts[i];
        if (line && measure(ctx,candidate).width > width) {result.push(line);line=parts[i];}
        else line=candidate;
        if (i<parts.length-1) {result.push(line);line='';}
      }
    }
    if (line) result.push(line);
  }
  return result;
}
function layoutText(ctx, text, options) {
  if (typeof text !== 'string' || !text.trim()) throw new Error('Nonempty text required');
  const {x=0,y=0,width,height,fontFamily,fontSize=42,lineHeight=1.25,strokeWidth=0}=options;
  requirePositive(width,'width');requirePositive(fontSize,'fontSize');requirePositive(lineHeight,'lineHeight');
  if (![x,y,strokeWidth].every(Number.isFinite) || strokeWidth<0 || !fontFamily) throw new Error('Invalid text geometry/font');
  const p=paddingValues(options.padding), inset=strokeWidth/2;
  const contentWidth=width-p.left-p.right-strokeWidth;
  requirePositive(contentWidth,'contentWidth');
  ctx.save();ctx.font=`${fontSize}px "${fontFamily}"`;ctx.textBaseline='alphabetic';ctx.textAlign='left';
  try {
    const lines=wrapText(ctx,text,contentWidth);
    const metrics=lines.map(s=>measure(ctx,s));
    const ascent=Math.max(...metrics.map(m=>m.ascent));
    const descent=Math.max(...metrics.map(m=>m.descent));
    const advance=Math.max(fontSize*lineHeight,ascent+descent+fontSize*.12);
    const requiredHeight=p.top+p.bottom+strokeWidth+ascent+descent+(lines.length-1)*advance;
    const boxHeight=height===undefined ? Math.ceil(requiredHeight) : height;
    requirePositive(boxHeight,'height');
    if (boxHeight+0.01<requiredHeight) throw new Error(`Text height overflow: needs ${requiredHeight.toFixed(2)}px, has ${boxHeight}px; enlarge/rewrite/split`);
    const inner={left:x+p.left+inset,top:y+p.top+inset,right:x+width-p.right-inset,bottom:y+boxHeight-p.bottom-inset};
    const placed=lines.map((value,i)=>{
      const m=metrics[i], px=inner.left+m.left,baseline=inner.top+ascent+i*advance;
      const ink={left:px-m.left,top:baseline-m.ascent,right:px+m.right,bottom:baseline+m.descent};
      if (value && (ink.left<inner.left-.01 || ink.top<inner.top-.01 || ink.right>inner.right+.01 || ink.bottom>inner.bottom+.01)) throw new Error('Glyph exceeds its parent text area');
      return {text:value,x:px,baseline,ink};
    });
    return {text,fontFamily,fontSize,lineHeight,box:{x,y,width,height:boxHeight},inner,padding:p,requiredHeight,lines:placed};
  } finally {ctx.restore();}
}
function drawText(ctx, layout, color='#142D48') {
  ctx.save();ctx.font=`${layout.fontSize}px "${layout.fontFamily}"`;ctx.textBaseline='alphabetic';ctx.textAlign='left';ctx.fillStyle=color;
  for (const line of layout.lines) if(line.text) ctx.fillText(line.text,line.x,line.baseline);
  ctx.restore();
}
function layoutBubble(ctx, {speaker,text,x=0,y=0,width=476,height,fontFamily='Paperlogy',fontSize=42,labelSize=25,padding=24,strokeWidth=3,labelGap=12}) {
  const p=paddingValues(padding),common={x,y,width,fontFamily,strokeWidth};
  const label=layoutText(ctx,speaker,{...common,fontSize:labelSize,padding:{...p,bottom:0}});
  const bodyY=y+label.box.height+labelGap;
  const body=layoutText(ctx,text,{...common,y:bodyY,fontSize,padding:{top:0,left:p.left,right:p.right,bottom:p.bottom}});
  const requiredHeight=Math.ceil(bodyY-y+body.box.height);
  if (height!==undefined && height<requiredHeight) throw new Error(`Speech bubble overflow: needs ${requiredHeight}px including label and padding; has ${height}px`);
  return {box:{x,y,width,height:height===undefined?requiredHeight:height},requiredHeight,label,body,tailExcludedFromTextArea:true};
}
function drawBubble(ctx, layout, {stroke='#064FA9',fill='#FFFFFF',radius=22,tail=true}={}) {
  const {x,y,width,height}=layout.box;
  ctx.save();ctx.fillStyle=fill;ctx.strokeStyle=stroke;ctx.lineWidth=3;
  // Keep the tail outside the body and never count it as lettering space.
  if(tail){ctx.beginPath();ctx.moveTo(x+70,y+height-4);ctx.lineTo(x+90,y+height+18);ctx.lineTo(x+112,y+height-4);ctx.fill();ctx.stroke();}
  ctx.beginPath();ctx.roundRect(x,y,width,height,radius);ctx.fill();ctx.stroke();ctx.restore();
  drawText(ctx,layout.label,stroke);drawText(ctx,layout.body);
}
function writeReport(reportPath, imagePath, layouts) {
  if (!layouts.length) throw new Error('No measured text layouts to report');
  const report={schema_version:1,engine:'actual-canvas-glyph-metrics',image:path.resolve(imagePath),image_sha256:crypto.createHash('sha256').update(fs.readFileSync(imagePath)).digest('hex'),text_blocks:layouts,scope:'All text must be rendered via measured layouts; final PNG still requires visual review.'};
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2),'utf8');return report;
}
module.exports={layoutText,drawText,layoutBubble,drawBubble,writeReport};
