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

显然此处`sub_401050`是关键的条件判断函数
![](https://img.h1kari.cn/blog/images/542d275fa8442dae4b2a4a49d3d9c8ce8b1f15329abf7fb1a19e92c5a78125c0.png)

根据循环体可判断第一个循环是做异或，第二个则是逐字符比较
![](https://img.h1kari.cn/blog/images/98841513f6fd3ed271fa370823e52b69c03e45d980275abfee2442d71e7a39a4.png)

其中`sub_401020`是利用循环获取字符长度
![](https://img.h1kari.cn/blog/images/3e91a4f69debbdd1735b7dab63a4297b8f88ce9f0ada5b1a930f4195684c56d4.png)

`sub_401000`则是获取初始的密钥
![](https://img.h1kari.cn/blog/images/01dc9d9ea5d6dd1da7ea15097e9706c8f06a044685accf5027b13cf86c9dad2a.png)

注意此处的ROL4是循环左移，且起初的`-2147024896`是__int32，在qalc下得补码，据此计算可得初始密钥为4
![](https://img.h1kari.cn/blog/images/e81a2b2c6c77154ad8b21fb5e549e1780c67808403631e67fb5c78a4a4ba1a8b.png)

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
![](https://img.h1kari.cn/blog/images/7e08dbf108e3426de5b3914a7119769874ac9bf94fd8be1bba632bf9a3a3af43.png)

最终即可得到flag`flag{R_y0u_H0t_3n0ugH_t0_1gn1t3@flare-on.com}`
![](https://img.h1kari.cn/blog/images/f86acfb84219c09571b69abac6933496fa8a180e8e6d9ef8acf0c4b907cf8cb4.png)