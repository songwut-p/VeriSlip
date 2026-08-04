# คู่มือติดตั้งและใช้งาน Local AI (Ollama + Qwen) บน WSL

> บันทึกจากการติดตั้งจริงบนเครื่อง Asus GL504GV | RTX 2060 6GB VRAM | RAM 40GB

---

## 1. เปิด WSL

มีหลายวิธี เลือกวิธีใดวิธีหนึ่ง:

- กด `Win + R` พิมพ์ `wsl` แล้ว Enter
- เปิด PowerShell / Terminal ของ Windows แล้วพิมพ์ `wsl`
- ใน VS Code กด `Ctrl+Shift+P` พิมพ์ `WSL: Connect to WSL`

---

## 2. ติดตั้ง Ollama

### ปัญหาที่เจอ & วิธีแก้

**ปัญหา 1: `sudo: Authentication failed`**
- เวลาพิมพ์ password ใน terminal จะไม่มีตัวอักษรขึ้นเลย (ไม่ใช่แม้แต่ `****`) เป็นเรื่องปกติ พิมพ์ password ของ user แล้วกด Enter ตรงๆ
- ถ้าลืม password จริงๆ ให้ reset ผ่าน PowerShell:
  ```powershell
  wsl -u root
  ```
  แล้วเปลี่ยน password:
  ```bash
  passwd songwut
  ```

**ปัญหา 2: `ERROR: This version requires zstd for extraction`**
- ต้องติดตั้ง zstd ก่อนรัน installer:
  ```bash
  sudo apt-get update
  sudo apt-get install zstd
  ```

### ติดตั้งจริง

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

ตรวจสอบว่าติดตั้งสำเร็จ:

```bash
ollama --version
```

---

## 3. เช็ค GPU ให้ Ollama เห็น

```bash
nvidia-smi
```

ถ้าเห็นข้อมูลการ์ดจอ (RTX 2060) ขึ้นมา แปลว่า WSL เห็น GPU แล้ว พร้อมใช้งาน
(ถ้าไม่เห็น ต้องติดตั้ง NVIDIA driver สำหรับ WSL ที่ฝั่ง **Windows** ไม่ใช่ในตัว WSL)

---

## 4. ดึงโมเดลมาใช้

```bash
# Qwen2.5 7B (เบา เร็ว ไม่มี thinking mode)
ollama pull qwen2.5:7b-instruct-q4_K_M

# Qwen3.5 9B (ใหม่กว่า มี thinking mode ในตัว)
ollama pull qwen3.5:9b
```

> หมายเหตุ: ชื่อ tag อาจเปลี่ยนได้ ให้เช็คที่ [ollama.com/library](https://ollama.com/library) ก่อนดึงจริงเสมอ

---

## 5. ทดสอบรันโมเดล

```bash
ollama run qwen2.5:7b-instruct-q4_K_M
```

หรือ

```bash
ollama run qwen3.5:9b
```

กด `Ctrl+D` เพื่อออกจาก session

---

## 6. ปิด Thinking Mode ของ Qwen3.5 (สำคัญ!)

### สิ่งที่ **ใช้ไม่ได้** (ห้ามเสียเวลาลอง)
- ตั้ง `SYSTEM` prompt ใน Modelfile สั่งให้ตอบตรงๆ — **ไม่มีผล** เพราะ thinking mode ควบคุมผ่าน chat template ไม่ใช่ system prompt

### วิธีที่ **ใช้ได้จริง**

**ผ่าน command line:**
```bash
ollama run qwen3.5:9b --think=false
```

**ผ่าน Python API:**
```python
import ollama

response = ollama.chat(
    model='qwen3.5:9b',
    messages=[{'role': 'user', 'content': 'ทดสอบภาษาไทย'}],
    think=False
)
print(response['message']['content'])
```

### ผลต่างที่วัดได้จริง (จากการทดสอบ)
| | Thinking mode เปิด | `--think=false` |
|---|---|---|
| GPU Utilization | 93% | 0% (idle หลังตอบ) |
| อุณหภูมิ GPU | 60°C | 52°C |
| ความเร็วตอบ | ช้า (มี "Thinking..." ยาว) | ตอบตรงทันที |

---

## 7. เรียกใช้ผ่าน Python (สำหรับต่อเข้าโปรเจกต์)

ติดตั้ง library:
```bash
pip install ollama
```

ตัวอย่างเรียกใช้:
```python
import ollama

response = ollama.chat(
    model='qwen2.5:7b-instruct-q4_K_M',
    messages=[{'role': 'user', 'content': ocr_text}]
)
print(response['message']['content'])
```

Ollama API รันอยู่ที่ `http://localhost:11434` โดย default

---

## 8. หลักการเลือกใช้ Local vs Cloud (Claude)

| งาน | ใช้ตัวไหน |
|---|---|
| RAG ตอบคำถามจากเอกสาร (routine) | Local (Qwen) |
| Parse field จาก OCR text ที่ตายตัว | Local (Qwen, ปิด thinking) |
| Debug logic ซับซ้อน / bug แปลกๆ | Cloud (Claude) |
| ออกแบบ architecture โปรเจกต์ | Cloud (Claude) |
| Context ยาว ต้องเข้าใจทั้งโปรเจกต์ | Cloud (Claude) |

**หลักคิด:** thinking mode / reasoning ช่วยงานที่มี ambiguity ต้องเลือกทางเดินหลายทาง (math, debug ซับซ้อน) แต่ไม่ช่วยงาน pattern-matching ตรงไปตรงมาแบบ parse field — เปิดไว้มีแต่เสียเวลา + VRAM โดยไม่ได้ความแม่นยำเพิ่ม

---

## 9. โมเดลที่พิจารณาไว้ (ตาม VRAM 6GB)

- **Qwen2.5-7B (Q4)** — ภาษาไทยดี ไม่มี thinking overhead เหมาะกับงาน RAG/parse ทั่วไป
- **Qwen3.5-9B** — ใหม่กว่า สถาปัตยกรรม hybrid, รองรับ multimodal, ต้องปิด thinking ด้วย `--think=false` สำหรับงานที่ต้องการความไว
- **DeepSeek-R1-Distill-Qwen-7B** — เหมาะกับงานที่ต้อง reasoning จริงๆ เช่น debug logic ซับซ้อน (ไม่เหมาะกับ parse field ทั่วไป)
- หลีกเลี่ยงโมเดล 13B+ บน VRAM 6GB เพราะจะ overflow ไป RAM มาก ทำให้ช้าเกินใช้งานจริง
