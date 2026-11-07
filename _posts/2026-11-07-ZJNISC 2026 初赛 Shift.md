---
layout: mypost
title: ZJNISC 2026 初赛 Shift
categories:
  - ReverseEngineering
  - WriteUp
  - C/CPP
extMath: false
---
_最新修改于  2026-11-07 21:01:46_

shift+f12可以明显看到base64码表和下方疑似是密文的内容以及输出的文本![](https://img.h1kari.cn/blog/images/c085e66c4b615d084f0d37fb295a187b980540a557066bdfbc1afa035d2e9c41.webp)

通过交叉引用可以确定，这里的unk_5340是base64码表，unk_5360是密文，unk5380是成功时输出的文本，unk_53A0是错误时输出的文本
![](https://img.h1kari.cn/blog/images/3a7a5c430a461b5fd7b840d7dbbfb4bd81ad1c381f14d7ad70bb4a27ceacbae0.webp)

阅读main函数可以发现，在读取明文flag后，调用了sub_25C4,随后在25C4中调用257A做了位移，那么将25C4改名为shift,特别注意此处shift的偏移是byte_50E0的0x28
![](https://img.h1kari.cn/blog/images/d95706eee6b9e58f38e74587eec04d76449de3b2a9f6dbf033ee258e8138210c.webp)

结合main以及后续的unk_5340的交叉引用还有sub_22c9的具体实现可以确定这是base64处理函数，随后就会对密文和明文做比较，然后输出对应的字符
![](https://img.h1kari.cn/blog/images/67b43d8a9c5f6c5c305617dae981c2b214fa0a39cead9d9ed0e054ea8454c46c.webp)

最后根据以上信息编写脚本即可得到flag是`DASCTF{b1a6ca60b0f01212cc1403050c78c6d0}`
![](https://img.h1kari.cn/blog/images/ddd3316ceac7baaffffa03e5face2a8bb9da8a6b349fe83118a1088b3e6631f7.webp)