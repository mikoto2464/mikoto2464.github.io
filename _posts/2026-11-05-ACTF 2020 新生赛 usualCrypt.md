---
layout: mypost
title: ACTF 2020 新生赛 usualCrypt
categories:
  - ReverseEngineering
  - WriteUp
  - XOR
extMath: false
---
_最新修改于  2026-11-05 01:29:31_

查看文件类型
```
> file base.exe
base.exe: PE32 executable for MS Windows 4.00 (console), Intel i386, 3 sections
```

观察main，显然可以看出关键的加密函数是`sub_401080`，且密文是位于0x40E0E4的字符串
![](https://img.h1kari.cn/blog/images/41a4b163c03c6e8c10f51641ff2143eac869f26d6169c78370f38eef872e5c9f.webp)

显然此处是base64加密
![](https://img.h1kari.cn/blog/images/0260fb94bfe2d81355c8ae0dacd159fada1bdb9c500b215fca9cb2fb75a1d309.webp)

可是此处定位到的码表却是标准的码表，考虑到标准base64码表出现在此类题的概率较小，那么下一步查看此处的交叉引用
![](https://img.h1kari.cn/blog/images/ac6e7ca77345643ecf884e9fbcec6c7787ba07059292642848f16aca0a89debb.webp)
![](https://img.h1kari.cn/blog/images/8ec2688451032de15d1f166dd9c9d0c01e0f59955de1ae7f2cd0b286466dcbd3.webp)

找到`sub_401000`，发现此处对base64码表进行动态修改
![](https://img.h1kari.cn/blog/images/b572b768f2e4252ea1292d5c68fd2a8b15e276aabe6b11656c502b22f03520bd.webp)

根据以上伪代码可以得到以下相应的计算码表的方法
```
data = [*'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/']
for i in range(6,15):
	x = data[10+i]
	data[10+i] = data[i]
	data[i] = x
```

根据以上密文就有以下代码，但是显然此处得到的并不是准确的flag
![](https://img.h1kari.cn/blog/images/3d8451cceeb3af3af1f2a83adfa01da054f6d6f0cf811a9f4bd92f7890d02043.webp)

观察发现，在return之前还调用了sub_401030函数，观察后可得知，此处是调换字母大小写
![](https://img.h1kari.cn/blog/images/60d18bc1f78528232e68b0c98c9f95ef2fe81a4d56836b253e0fb68950900549.webp)

![](https://img.h1kari.cn/blog/images/f58b0a6525cf86d0f56cc174e5455a28ca88c4a434543e286a2dc956a376a4b2.webp)

那么也只需要调换密文的大小写，随后再做base64加密即可得到最终的flag`flag{bAse64_h2s_a_Surprise}`
![](https://img.h1kari.cn/blog/images/55d94ed8bcb789f463e42caf6c7f694eaba86395f90e8130f1619c5bc94ebf63.webp)