---
layout: mypost
title: FlareOn4 login
categories:
  - ReverseEngineering
  - WriteUp
  - XOR
extMath: false
---
_最新修改于  2026-11-05 01:28:32_

查看文件类型
```
> file IgniteMe.exe
IgniteMe.exe: PE32 executable for MS Windows 5.01 (console), Intel i386, 3 sections
```

显然此处`sub_401050`是关键的条件判断函数
![](Pasted%20image%2020261105011206.png)

根据循环体可判断第一个循环是做异或，第二个则是逐字符比较
![](Pasted%20image%2020261105011316.png)

其中`sub_401020`是利用循环获取字符长度
![](Pasted%20image%2020261105011523.png)

`sub_401000`则是获取初始的密钥
![](Pasted%20image%2020261105011538.png)

注意此处的ROL4是循环左移，且起初的`-2147024896`是__int32，在qalc下得补码，据此计算可得初始密钥为4
![](Pasted%20image%2020261105011955.png)

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
![](Pasted%20image%2020261105012605.png)

最终即可得到flag`flag{R_y0u_H0t_3n0ugH_t0_1gn1t3@flare-on.com}`
![](Pasted%20image%2020261105012737.png)