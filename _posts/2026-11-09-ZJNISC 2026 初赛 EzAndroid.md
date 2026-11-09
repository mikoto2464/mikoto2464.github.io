---
layout: mypost
title: ZJNISC 2026 初赛 EzAndroid
categories:
  - ReverseEngineering
  - WriteUp
  - Android
  - Lua
  - XTEA
  - XOR
extMath: false
---
_最新修改于  2026-11-09 20:15:05_

打开apk后可以发现此处用的是Androlua框架
![](Pasted%20image%2020261107215717.png)

且在assets目录下发现了大量lua文件
![](Pasted%20image%2020261108115039.png)

将main.lua给dump出来后，尝试用unluac解密可以发现出现错误
![](Pasted%20image%2020261108185914.png)

注意到文件开头是`1B 45 67 7A`
![](Pasted%20image%2020261108185724.png)

而正常lua文件编译后应该是`1B 4C 75 61`，将以上二者异或后则有异或密钥的前三位。而此密钥有明显的规律是0x09的倍数
```text
0x45 ^ 0x4c = 0x09
0x67 ^ 0x75 = 0x12
0x7a ^ 0x61 = 0x1b
```

同理可以发现，其他的文件也是类似逻辑，只是初始值不同而已，也就是此处的算法是：
```python
step = encrypted[1] ^ 0x4c
plain[i] = encrypted[i] ^ ((i * step) % 255)
```

那么据此即可从apk中提取解密后的lua脚本
```python
import os
import zipfile
PATH = 'decoded_lua'
def decrypt_lua(data: bytes) -> bytes:
    if data[0] != 0x1B:
        return data
    step = data[1] ^ 0x4C
    return bytes([data[0]]) + bytes(
        value ^ ((index * step) % 255)
        for index, value in enumerate(data[1:], 1)
    )
os.makedirs(PATH, exist_ok=True)
with zipfile.ZipFile('ezAndroid.apk', "r") as apk:
    for name in apk.namelist():
        if not name.endswith(".lua"):
            continue
        output_path = os.path.join(PATH, name)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(decrypt_lua(apk.read(name)))
        print(f"[+] {name}")
```
![](Pasted%20image%2020261108190810.png)

随后调用unluac完成反编译 以及我这里自制的一个lua可读性增强脚本 即可得到完整的lua代码
![](Pasted%20image%2020261109142456.png)
![](Pasted%20image%2020261109142556.png)

结合root.lua和pz.lua可以看到主要逻辑如下
![](Pasted%20image%2020261109143023.png)

随后在pz.lua中可以发现明显的TEA系列加密特征，Delta是2161537835，轮次是38，此处用到的key是L8_1，密文是oianxasdavsdvasd，特别注意到此处是先算total再算v0再算v1，这和标准的XTEA稍微有些不同，所以解密时也要注意先处理v1再处理v0再处理total，特别地在38轮后还做了一次异或，所以解密时要先做异或再做xtea
![](Pasted%20image%2020261109201045.png)

注意上图所有数字常量是已经计算过的，此处算式是由114514组成的表达式，算式生成可以用itorr的恶臭数字论证器生成（喜
![](Pasted%20image%2020261109153742.png)

综合以上信息写出脚本，最终可得到flag是`7a5e-55e45-1671e-df3b7-cd7a1-6f1e-27fc`
### POC
```python
# solve.py
def xtea_decrypt(data, key, rounds=32, delta=0x9E3779B9):
    mask = 0xFFFFFFFF
    out = b""
    for offset in range(0, len(data), 2):
        v0, v1 = data[offset : offset + 2]
        v0 = (v0 ^ 14) & mask
        v1 = (v1 ^ 17) & mask
        total = (delta * rounds) & mask
        for _ in range(rounds):
            v1 = (
                v1 - ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (total + key[(total >> 11) & 3]))
            ) & mask
            v0 = (
                v0 - ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (total + key[total & 3]))
            ) & mask
            total = (total - delta) & mask
        out += v0.to_bytes(4, byteorder="big")
        out += v1.to_bytes(4, byteorder="big")
    return out


data = [
    863918170,
    366827450,
    2944604520,
    1314064158,
    2534040034,
    1250268803,
    3402278143,
    1361039932,
    3087907484,
    3107271874,
]
key = [5976, 40857, 3298229483, 1500946329]
result = xtea_decrypt(data, key, rounds=38, delta=2161537835)

print(result)
```

```
# extract_lua.py
import os
import zipfile

PATH = "decoded_lua"


def decrypt_lua(data: bytes) -> bytes:
    if data[0] != 0x1B:
        return data
    step = data[1] ^ 0x4C
    return bytes([data[0]]) + bytes(
        value ^ ((index * step) % 255) for index, value in enumerate(data[1:], 1)
    )


os.makedirs(PATH, exist_ok=True)
with zipfile.ZipFile("ezAndroid.apk", "r") as apk:
    for name in apk.namelist():
        if not name.endswith(".lua"):
            continue
        encrypted = apk.read(name)
        decrypted = decrypt_lua(encrypted)
        output_path = os.path.join(PATH, name)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(decrypted)
        print(f"[+] {name}")
```

```python
# disassemble_lua.py 
import os

for root, dirs, files in os.walk("."):
    for file in files:
        if not file.endswith(".lua") or not "decoded_lua" in root:
            continue
        src_path = os.path.join(root, file)
        dest_path = os.path.join(root.replace("decoded_lua", "disassembled_lua"), file)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        os.system(f"unluac {src_path} > {dest_path}")
        print(f"[+] {dest_path}")
```