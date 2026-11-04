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
![](https://img.h1kari.cn/blog/images/6d36f697404acab74186f3a8cce0a2c0754f0007ff5ba55577a8ce593aa84d34.png)

查看此处的Hex View 可以简单猜测此处0x032A~0x0349是flag
![](https://img.h1kari.cn/blog/images/b04cdfa8a5c367d16213bf8c061e00498892d0789bb4582eee20fdba41b0d533.png)

查看上述0x0324"DASCTF"的IDA View，并定位到右侧的引用
![](https://img.h1kari.cn/blog/images/c9dca28426aee95cf941ac6b91f4e45b8433aeb347166e2aef1ba11ab05f6825.png)

查看引用处的汇编代码
![](https://img.h1kari.cn/blog/images/6b480ff81f002ee42fc991b6696a0b76e98bcd0643b116b79968f4de8b9c4311.png)

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
![](https://img.h1kari.cn/blog/images/d94a56f27aa5cced78fb7a5085b976b3d69e41eba20c135788f31a30ff684f87.png)


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
![](https://img.h1kari.cn/blog/images/4b98a17997f2849bcf883c77ecb698db756b100dcf7a4c70c20caee0a09e8dee.png)

所以此处的核心加密实际上很简单
```
flag = b'someflag'
key = b'DASCTF'

for i in range(len(flag)):
    print(chr(flag[i] ^ key[i % len(key)]), end="")
```

又因为异或运算的可逆性 所以只需替换flag为密文即可解得flag
`DASCTF{H0wfUnnytheDosSnakeis!!!}`
![](https://img.h1kari.cn/blog/images/2b132832d75b3a2d0be2dcaf89b42e96df34146947ece63e1308c14c44ee1136.png)
