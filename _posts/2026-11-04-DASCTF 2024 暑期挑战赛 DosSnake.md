---
layout: mypost
title: DASCTF 2024 暑期挑战赛 DosSnake
categories:
  - ReverseEngineering
  - WriteUp
  - ASM
  - XOR
extMath: false
---
_最新修改于  2026-11-05 00:20:29_

查看文件类型
```
> file Game.exe
Game.exe: MS-DOS executable, MZ for MS-DOS
```

IDA打开后shift+F12可以看到
![](1.png)

查看此处的Hex View 可以简单猜测此处0x032A~0x0349是flag
![](2.png)

查看上述0x0324"DASCTF"的IDA View，并定位到右侧的引用
![](3.png)

查看引用处的汇编代码
![](4.png)

根据下方的
```
cmp    al, 0               ; 根据al-0设置标志 ZF=0或ZF=1
jz     short locret_10609  ; ZF=1时跳转到locret_10609 即al==0时跳转

mov    ah, 0Eh             ; 设置输出内容的功能号
int    10h                 ; 输出al中的字符
inc    si                  ; 索引自增
jmp    short loc_105FC     ; 继续读取字符并输出
```
可知，此处逻辑是循环输出所有字符直到输出的字符为0
![](5.png)


此处输出部分向上即可找到关键代码
```
loc_105E4:
mov    cx, 20h         ; 设置loop的轮次 即20
lea    si, aDasctf+6   ; 设置si为0x32A 即密文开头第一个字符的内存地址
lea    di, aDasctf     ; 设置di为0x324 即密钥开头第一个字符的内存地址

mov    al, [si]        ; 将al设置为si对应内存地址的字符
xor    al, [di]        ; 将al与di对于内存地址的字符做异或 注意此时al为明文字符
mov    [si], al        ; 设置si对应内存地址的字符为al
inc    si              ; si自增1
inc    di              ; di自增1
cmp    di, 32Ah        ; 根据di-0设置标志 ZF=0或ZF=1
jnz    short loc_105F6 ; ZF=0时跳转到loc_105F6 即di!=0x32A时跳转
lea    di, aDasctf     ; 设置di为0x324 此处是为了实现密钥DASCTF的循环使用

loc_105F6:
loop   loc_105E4       ; cx==0时继续执行下方代码，否则回到loc_105E4
```
![](6.png)

所以此处的核心加密实际上很简单
```
flag = b'someflag'
key = b'DASCTF'

for i in range(len(flag)):
    print(chr(flag[i] ^ key[i % len(key)]), end="")
```

又因为异或运算的可逆性 所以只需替换flag为密文即可解得flag
`DASCTF{H0wfUnnytheDosSnakeis!!!}`
![](7.png)
