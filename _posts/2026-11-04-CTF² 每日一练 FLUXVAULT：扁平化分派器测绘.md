---
layout: mypost
title: CTF² 每日一练 FLUXVAULT：扁平化分派器测绘
categories:
  - ReverseEngineering
  - WriteUp
  - Javascript
extMath: false
---
_最新修改于  2026-11-06 20:24:08_

在核心区段图的`DISPATCH CORE`可以看到
```
var T=[0x41,0x37,0xf7,0x19,0x7c,0xb9,0x3f,0xf8];
var D=[0xd9,0x15,0xce,0x57,0x15,0xce,0x59,0x3c];
function ck(k){
 var s=0x2E,i=0,a=0x07,c=0,v=0;
 while(1){ switch(s){
  case 0x16: c=k.charCodeAt(5+i); var v=(a*31+c)%251;
  case 0x2E: i=0; a=0x07; if(k.length!==13||k.slice(0,5)!=="FLUX-"){s=0x99;break;} s=0x11; break;
  case 0x11: c=k.charCodeAt(5+i); if((a*31+c)%251!==T[0]){s=0x99;break;} a=T[0]; i++; s=0x12; break;
  case 0x99: return 0;
  case 0x14: c=k.charCodeAt(5+i); a=(a+42)%251; if((a*31+c)%251!==T[3]){s=0x99;break;} a=T[3]; i++; s=0x18; break;
  case 0x2A: c=k.charCodeAt(5+i); if((a*17+c)%251!==D[i]){s=0x99;break;} a=D[i]; i++; s=(i>7)?0x7F:0x2A; break;
  case 0x18: c=k.charCodeAt(5+i); if((a*31+c)%251!==T[4]){s=0x99;break;} a=T[4]; i++; s=0x16; break;
  case 0x5C: a=(a*3+11)%251; s=0x2A; break;
  case 0x12: c=k.charCodeAt(5+i); if((a*31+c)%251!==T[1]){s=0x99;break;} a=T[1]; i++; s=0x15; break;
  case 0x17: c=k.charCodeAt(5+i); if((a*31+c)%251!==T[6]){s=0x99;break;} a=T[6]; i++; s=0x1A; break;
  case 0x7F: return 1;
  case 0x2B: v=(v+5)%251; if(v!==T[5]){s=0x99;break;} a=T[5]; i++; s=0x17; break;
  case 0x15: c=k.charCodeAt(5+i); if((a*31+c)%251!==T[2]){s=0x99;break;} a=T[2]; i++; s=0x14; break;
  case 0x1A: c=k.charCodeAt(5+i); if((a*31+c)%251!==T[7]){s=0x99;break;} a=T[7]; i++; s=0x7F; break;
 }}
ck(K);
```

显然此处是一个状态机，且注意到判断字符的结构如下
```
if(condition){s=0x99;break;}
```

为了方便修改，此处将条件作为lambda然后通过简单遍历获取字符![](https://img.h1kari.cn/blog/images/f7a3fb46df1b1dd1ae69dba13479a5678bad649a89885e1cfa0c4a8f05833f9c.webp)

特别注意0x16，这里仅仅是简单做个计算，随后则不改变状态，但是查看这里v的引用可以发现有且只有0x2B引用了v做了后续计算，也就是说此处0x16出现了断层。那么只需将0x18的下一步改为0x2B且将0x16的计算到0x2B即可走完全链路
![](https://img.h1kari.cn/blog/images/fe0d2f8155be7d888fbed6931cc01eaa39f3e5e35f22378f857d32dbbf195808.webp)

综上得出脚本，随即得到flag`FLUX-c00ffee4`
![](https://img.h1kari.cn/blog/images/3d5ab8afabaab297a32c1749d97577867c946d87a0f88acd223bfaf8f7bda047.webp)
```
import sys

standard = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789`~!@#$%^&*()_+-=[]{}\\|;':\",./<>?"
T = [0x41, 0x37, 0xF7, 0x19, 0x7C, 0xB9, 0x3F, 0xF8]
D = [0xD9, 0x15, 0xCE, 0x57, 0x15, 0xCE, 0x59, 0x3C]
s = 0x2E
i = 0
a = 0x07
c = 0
v = 0
flag = [""] * 8


def getflag(equation):
    for s in standard:
        if equation(s):
            return chr(s)
    return "0"


while True:
    match s:
        case 0x2E:
            i = 0
            a = 0x07
            s = 0x11
        case 0x11:
            flag[i] = getflag(lambda s: (a * 31 + s) % 251 == T[0])
            a = T[0]
            i += 1
            s = 0x12
        case 0x99:
            print(flag)
            sys.exit()
        case 0x14:
            a = (a + 42) % 251
            flag[i] = getflag(lambda s: (a * 31 + s) % 251 == T[3])
            s = 0x99
            a = T[3]
            i += 1
            s = 0x18
        case 0x2A:
            flag[i] = getflag(lambda s: (a * 17 + s) % 251 == D[i])
            a = D[i]
            i += 1
            s = 0x7F if i > 7 else 0x2A
        case 0x18:
            flag[i] = getflag(lambda s: (a * 31 + s) % 251 == T[4])
            a = T[4]
            i += 1
            s = 0x2B
        case 0x5C:
            a = (a * 3 + 11) % 251
            s = 0x2A
        case 0x12:
            flag[i] = getflag(lambda s: (a * 31 + s) % 251 == T[1])
            a = T[1]
            i += 1
            s = 0x15
        case 0x17:
            flag[i] = getflag(lambda s: (a * 31 + s) % 251 == T[6])
            a = T[6]
            i += 1
            s = 0x1A
        case 0x7F:
            print("".join(flag))
            sys.exit()
        case 0x2B:
            flag[i] = getflag(lambda s: ((a * 31 + s) % 251 + 5) % 251 == T[5])
            a = T[5]
            i += 1
            s = 0x17
        case 0x15:
            flag[i] = getflag(lambda s: (a * 31 + s) % 251 == T[2])
            a = T[2]
            i += 1
            s = 0x14
        case 0x1A:
            flag[i] = getflag(lambda s: (a * 31 + s) % 251 == T[7])
            a = T[7]
            i += 1
            s = 0x7F
```