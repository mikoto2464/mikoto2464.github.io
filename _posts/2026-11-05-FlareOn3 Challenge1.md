---
layout: mypost
title: FlareOn3 Challenge1
categories:
  - ReverseEngineering
  - WriteUp
  - C/CPP
  - Base64
extMath: false
---
_最新修改于  2026-11-05 15:38:07_

查看文件类型
```
> file
challenge1.exe: PE32 executable for MS Windows 5.01 (console), Intel i386, 6 sections
```

在main中可以观察到密文和加密函数`sub_401260`
![](https://img.h1kari.cn/blog/images/c7086b3d7d69aa58abf5363757d9a19731407b4d1167e4590935c2eb52d48e71.webp)

不难看出此处是base64，后面是补码
![](https://img.h1kari.cn/blog/images/1219af6c385e3e2d949c3f6001daf4a752ffafb73637904fd7e9bbcd6da298f9.webp)

将0x413000处的base64码表dump出来后即可得到flag`flag{sh00ting_phish_in_a_barrel@flare-on.com}`
![](https://img.h1kari.cn/blog/images/2e1e4676fc09ddf04d7d0f240d85bbc29c29a873488f95354d3f0b3576521de6.webp)

![](https://img.h1kari.cn/blog/images/55bb1a32f8f5e3c7469477eab894fa0202de7c0c7440942268c390cc78c172bd.webp)