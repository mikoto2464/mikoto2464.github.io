---
layout: mypost
title: FlareOn4 IgniteMe
categories:
  - ReverseEngineering
  - WriteUp
  - XOR
extMath: false
---
_最新修改于  2026-11-05 01:29:31_

查看文件类型
```
> file IgniteMe.exe
IgniteMe.exe: PE32 executable for MS Windows 5.01 (console), Intel i386, 3 sections
```

显然此处`sub_401050`是关键的条件判断函数![](https://img.h1kari.cn/blog/images/6612feb281d22e6f80d9b2f2a85a7da4b1b1fad5cd4a34959ff8583b64cb396d.webp)

根据循环体可判断第一个循环是做异或，第二个则是逐字符比较
![](https://img.h1kari.cn/blog/images/6a597e129cedc79fe730b9dd81c4aac779c8cadc43091ecafbaabb05865621c5.webp)

其中`sub_401020`是利用循环获取字符长度
![](https://img.h1kari.cn/blog/images/66a0d9eb10f4f9183a41dfebbb1a4d5a5a0f58e6b4f35ffb08677d9b04d0d4d1.webp)

`sub_401000`则是获取初始的密钥
![](https://img.h1kari.cn/blog/images/c7f58fb9eb6e2f452bd4e7fe9a3f3e56ba5bfacfbc886931d4225c29116f3e00.webp)

注意此处的ROL4是循环左移，且起初的`-2147024896`是__int32，在qalc下得补码，据此计算可得初始密钥为4
![](https://img.h1kari.cn/blog/images/bbedd313eddff9270457598ced09aab8fdbc42bcb18336f73dc5134862a0eea2.webp)

接着阅读上述异或循环体可知，加密方式如下
```
key = 4
result = b""
for i in reversed(range(len(data))):
    d = data[i] ^ key
    result += d
    key = s
```

接着dump出`byte_403000`的密文，从`0x40300`到`0x403027`。
![](https://img.h1kari.cn/blog/images/b5584fe4d58e2d880d6af7f147db119dd068250f0057c4ae994a235a3131e830.webp)

最终即可得到flag`flag{R_y0u_H0t_3n0ugH_t0_1gn1t3@flare-on.com}`
![](https://img.h1kari.cn/blog/images/340ae7e407551a005187f23569d4ff5fbb620ef662241a90f42865e69eb4c8ef.webp)