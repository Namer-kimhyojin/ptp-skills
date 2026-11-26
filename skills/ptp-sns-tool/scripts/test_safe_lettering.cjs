'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {createCanvas,GlobalFonts}=require('@napi-rs/canvas');
const {layoutText,drawText,layoutBubble,drawBubble,writeReport}=require('./safe_lettering.cjs');
const font=path.join(__dirname,'../assets/fonts/paperlogy/Paperlogy-7Bold.ttf');
assert(GlobalFonts.registerFromPath(font,'PTP-Test'));
const canvas=createCanvas(1080,600),ctx=canvas.getContext('2d');
const family='PTP-Test';let count=0;
function check(fn){fn();count++;}
const sentence='주관기업과 수요처는 같은 시·군!';
const small={speaker:'테오',text:sentence,x:48,y:40,width:476,height:124,fontFamily:family,fontSize:36};
check(()=>assert.throws(()=>layoutBubble(ctx,small),/overflow/));
const bubble=layoutBubble(ctx,{...small,height:undefined});
check(()=>assert(bubble.requiredHeight>124));
check(()=>assert(bubble.body.lines.every(l=>l.ink.bottom<=bubble.body.inner.bottom+.01)));
check(()=>assert(bubble.body.lines.some(l=>l.text.includes('시·군!'))));
check(()=>assert.throws(()=>layoutText(ctx,'반드시\n전체 높이를\n확인합니다',{x:0,y:0,width:200,height:60,fontFamily:family,fontSize:36,padding:20}),/height overflow/));
check(()=>assert.throws(()=>layoutText(ctx,'name@ptp.or.kr',{width:100,fontFamily:family,fontSize:36}),/Protected token/));
check(()=>{
  const l=layoutText(ctx,'아주긴한글단어도공간을넘지않도록나눕니다',{width:200,fontFamily:family,fontSize:36});
  assert(l.lines.length>1);assert.equal(l.lines.map(x=>x.text).join(''),'아주긴한글단어도공간을넘지않도록나눕니다');
});
check(()=>assert.throws(()=>layoutText(ctx,'확인',{width:40,fontFamily:family,padding:24}),/contentWidth/));
check(()=>{
  const l=layoutText(ctx,'가독성과 여백\n\n한 줄을 더 둡니다',{width:476,fontFamily:family,fontSize:36});
  assert(l.lines.some(x=>x.text===''));assert(l.lines.every(x=>x.ink.right<=l.inner.right+.01));
});
const output=process.argv[2];
const folder=output ? path.resolve(output) : fs.mkdtempSync(path.join(os.tmpdir(),'ptp-lettering-'));
fs.mkdirSync(folder,{recursive:true});
ctx.fillStyle='#FAF7F0';ctx.fillRect(0,0,1080,600);
drawBubble(ctx,bubble);
const second=layoutBubble(ctx,{speaker:'피오',text:'참여의향서도 함께 챙기자.',x:556,y:40,width:476,fontFamily:family,fontSize:36});
// Align both backgrounds to the taller measured bubble without reducing text.
second.box.height=bubble.box.height;
drawBubble(ctx,second,{stroke:'#B85000'});
const title=layoutText(ctx,'실제 글꼴로 이름표·대사·아래 여백까지 측정',{x:48,y:260,width:984,fontFamily:family,fontSize:42,padding:0});
drawText(ctx,title);
const note=layoutText(ctx,'고정 124px 박스는 차단하고 필요한 높이로 확장합니다.',{x:48,y:360,width:984,fontFamily:family,fontSize:34,padding:0});
drawText(ctx,note);
const image=path.join(folder,'lettering-proof.png');fs.writeFileSync(image,canvas.toBuffer('image/png'));
const report=writeReport(path.join(folder,'lettering-report.json'),image,[bubble.label,bubble.body,second.label,second.body,title,note]);
check(()=>assert.equal(report.text_blocks.length,6));
console.log(JSON.stringify({passed:count,old_fixed_height:124,required_height:bubble.requiredHeight,image,report:path.join(folder,'lettering-report.json')}));
if(!output) fs.rmSync(folder,{recursive:true,force:true});
