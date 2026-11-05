---
layout: mypost
title: GXYCTF 2019 luck_guy
categories:
  - ReverseEngineering
  - WriteUp
  - XOR
extMath: false
---
_最新修改于  2026-11-05 15:08:09_

查看文件类型
```
> file luck_guy
luck_guy: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, for GNU/Linux 2.6.32, BuildID[sha1]=38f6b7066f73e3b41dca3ab5b6da405f8edf2ec5, not stripped
```

观察main，不难发现此处v4是输入的数字且patch_me是关键的函数
![](https://img.h1kari.cn/blog/images/6c3c55a0c5e21904bb655667a1c1eab571650ae9f9cce155bcfffa28ba2c29ee.webp)

紧接着此处要求输入数字是偶数才能接着获取flag
![](https://img.h1kari.cn/blog/images/ef1cffd86a2963c3874a06f135d5c3482056ed37bade0a35042d3f0228ff3427.webp)

试运行后发现在大多数情况下反复输出五次`emmm,you can't find flag 23333`
![](https://img.h1kari.cn/blog/images/461cfe0ec7af093e044d0e44f62739f38c3161793577ced321dfbb4b71ad5938.webp)

观察此处switch即可得到基本逻辑：先执行case 4将s的值赋予f2，再执行case 5对字符做偏移处理，最后合并输出
![](https://img.h1kari.cn/blog/images/77ac54207fe26edc5701a0c8548bc9ca1d208adb30612b43ac920edbc91484fb.webp)

据此编写python脚本即可得到flag`GXY{do_not_hate_me}`
```
f2 = 0x7F666F6067756369.to_bytes(8, byteorder="little")
print("GXY{do_not_", end="")
for i in range(8):
    print(chr(f2[i] - (i % 2 + 1)), end="")
```
![](https://img.h1kari.cn/blog/images/6972e916d322064f5de6f6dbc6fc92eb4ccffdf9029da47423e256ea45620f40.webp)