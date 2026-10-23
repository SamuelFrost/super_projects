# Choosing a Gemma Model & Resource Settings

To run Gemma locally, copy the example file:
```sh
cp .devcontainer/docker_compose_configuration_customizations/lllm/compose.lllm.override.example.yaml \
   .devcontainer/docker_compose_configuration_customizations/lllm/compose.lllm.override.yaml
```

Inside `compose.lllm.override.yaml`, you configure three main settings:
1. `GEMMA_MODEL`: Which Gemma 4 model size to download (`e2b`, `e4b`, `12b`, `26b`, `31b`).
2. `mem_limit`: The maximum system RAM Docker is allowed to use.
3. `OLLAMA_CONTEXT_LENGTH`: How much text (chat history + code) the model remembers at once.

`OLLAMA_KEEP_ALIVE` controls how long that loaded model stays in memory after the last request. The tracked compose file sets it to `5m`, which is Ollama's own default. The example override sets `20m`. `-1` keeps the model loaded until the local-llm container stops. Loading it again rebuilds the context slot, which is the slow part of the next request.

---

## Quick Reference

Picking your model and resources basically boils down to adding up your fast available memory (VRAM and/or system RAM) and picking a set of trade-offs that make sense for you within that constraint (VRAM is nice, but system RAM feels fine for most use-cases so don't stress over it; using memory swap will generally feel very slow, but may fit some use cases). Here's a table for a quick choice of model and resource settings.

| Your Hardware | Recommended Model | `mem_limit` | `OLLAMA_CONTEXT_LENGTH` | Expected Speed |
|---------------|-------------------|-------------|-------------------------|----------------|
| **16 GB of system RAM (inference on the CPU, or a Mac)** | `gemma4:e2b` | `12g` | `8192` (or `4096` if tight) | Moderate |
| **32 GB of system RAM (inference on the CPU, or a Mac)** | `gemma4:e4b` | `16g` | `8192` | Moderate |
| **GPU with 6–8 GB of VRAM** | `gemma4:e2b` (or `e4b` hybrid) | `8g` (or `10g`) | `8192` | Fast |
| **GPU with 12–16 GB of VRAM** | `gemma4:e4b` or `gemma4:12b` | `8g` | `8192` | Very fast |
| **GPU with 24 GB or more of VRAM** | `gemma4:26b` | `8g` | unset (Ollama auto 32k) | Very fast |

> **Mac Users**: Docker Desktop on macOS cannot pass Apple Silicon GPUs to Linux containers. The model always runs on the CPU and uses system RAM.

---

## Step 1: Check Your Hardware Specs

Run these commands in a terminal **on your host computer** (outside the devcontainer):

### Windows (PowerShell)
```powershell
# System RAM in GB:
(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB

# NVIDIA GPU / VRAM:
nvidia-smi
```

### macOS (Terminal)
```sh
# System RAM:
system_profiler SPHardwareDataType | grep "Memory:"
```

### Linux / WSL2
```sh
# System RAM:
free -h

# GPU / VRAM:
nvidia-smi   # NVIDIA
rocm-smi     # AMD
```

---

## Step 2: Configure `compose.lllm.override.yaml`

Choose the scenario below that matches your machine:

### Scenario A: CPU Only (No GPU, or running on macOS)

All model layers and context buffers run in system RAM. 

To size `mem_limit`:
$$\text{mem\_limit} \approx \text{Weight-file download} + \text{KV cache} + \text{1–2 GB of container RAM for runtime overhead}$$

Ensure your host machine retains enough headroom for your specific workload (OS, IDE, builds, browser).

| Model Tag | Q4_K_M weight-file download | Recommended `mem_limit` (container RAM, ~8k context) | Notes |
|-----------|----------------------------|-----------------------------------------------------|-------|
| `gemma4:e2b` | 4.6 GB of weights | `10g`–`12g` | Lightweight; suitable for resource-constrained setups |
| `gemma4:e4b` | 6.6 GB of weights | `14g`–`16g` | Balanced option for code and general assistance |
| `gemma4:12b` | 8.0 GB of weights | `14g`–`16g` | Stronger reasoning; denser memory access |
| `gemma4:26b` | 18 GB of weights | `22g`–`24g` | High quality Mixture-of-Experts |
| `gemma4:31b` | 20 GB of weights | `28g`–`32g` | Largest dense variant |

*Example override for 16 GB of system RAM, with inference on the CPU or on a Mac:*
```yaml
services:
  local-llm:
    mem_limit: 12g
    environment:
      GEMMA_MODEL: gemma4:e2b
      OLLAMA_CONTEXT_LENGTH: "8192"
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:e2b
```

---

### Scenario B: Dedicated GPU (Fits the Entire Model)

If your graphics card has enough VRAM, inference runs entirely on the GPU for maximum speed. System RAM is only used for light container overhead.

1. Uncomment your GPU in `compose.lllm.override.yaml` (e.g. `gpus: all` for NVIDIA).
2. Set `mem_limit: 8g` for any model tag that fits in VRAM.

| Model Tag | Required GPU VRAM | `mem_limit` |
|-----------|-------------------|-------------|
| `gemma4:e2b` | 8 GB of VRAM or more | `8g` of container RAM |
| `gemma4:e4b` | 12 GB of VRAM or more | `8g` of container RAM |
| `gemma4:12b` | 16 GB of VRAM or more | `8g` of container RAM |
| `gemma4:26b` | 24 GB of VRAM or more | `8g` of container RAM |
| `gemma4:31b` | 32 GB of VRAM or more | `8g` of container RAM |

*Example override for an NVIDIA GPU with 8 GB of VRAM:*
```yaml
services:
  local-llm:
    mem_limit: 8g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:e2b
      OLLAMA_CONTEXT_LENGTH: "8192"
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:e2b
```

---

### Scenario C: Hybrid (GPU VRAM + System RAM)

If your GPU cannot fit the whole model, Ollama automatically offloads whatever layers fit into VRAM and runs the rest in system RAM.

**Sizing `mem_limit`:**
$$\text{mem\_limit} \approx (\text{Weight-file download} - \text{GPU VRAM}) + \text{KV cache} + \text{1–2 GB of container RAM for headroom}$$

Ensure your host has enough unallocated RAM left over for your host environment.

| Model Tag | GPU VRAM | Estimated `mem_limit` (with ~8k context) |
|-----------|----------|-----------------------------------------|
| `gemma4:e4b` (6.6 GB of weights) | 8 GB of VRAM | `6g`–`8g` of container RAM |
| `gemma4:12b` (8.0 GB of weights) | 4–6 GB of VRAM | `8g`–`10g` of container RAM |
| `gemma4:26b` (18 GB of weights) | 8 GB of VRAM | `14g`–`16g` of container RAM |
| `gemma4:26b` (18 GB of weights) | 12 GB of VRAM | `10g`–`12g` of container RAM |
| `gemma4:26b` (18 GB of weights) | 16 GB of VRAM | `6g`–`8g` of container RAM |

---

## Tradeoffs and optimizations

### Understanding Context Length (`OLLAMA_CONTEXT_LENGTH`)

Context length is the total number of tokens (words and code snippets) the model can hold in working memory across your prompt and its reply.

- **Tokens vs. Words**: 1 token is roughly 0.75 words. An `8192` token window fits several thousand words—plenty for typical chats and editing a few code files.
- **Where it lives**: It creates an active memory buffer (KV cache). When running on GPU, it uses VRAM. When running on CPU (or when VRAM is full), it uses system RAM and counts against `mem_limit`.
- **Trained Maximums**: Gemma 4 models support up to 128K tokens (`e2b`, `e4b`) or 256K tokens (`12b`, `26b`, `31b`). The cache formula below is the KV-cache cost of that window. On `e2b` the full 128K-token KV cache is under 1 GB of KV cache before `q8_0` or `q4_0` compression.

#### How the number correlates to memory usage

The weights stay the same size. Cache size is what tracks `OLLAMA_CONTEXT_LENGTH`. This holds for fp16, Ollama's default, once the context is at least as long as the model's sliding window.

- **Parallel requests** is `OLLAMA_NUM_PARALLEL`. The default is `1`. Each request gets its own cache.
- **Sliding-window cache** is the memory for layers that only keep the last 512 or 1024 tokens. It stops growing once the context passes that window.
- **Full-attention cache** is the memory added per token by the layers that keep the whole context.
- **Context tokens** is `OLLAMA_CONTEXT_LENGTH`, cut down to the model's ceiling when the setting is higher.

```
cache_MiB = parallel_requests × (sliding_window_MiB + full_attention_KiB_per_token × context_tokens / 1024)
```

| Model | Sliding-window cache (MiB) | Full-attention cache (KiB/token) | Window | Ceiling |
|-------|----------------------------|----------------------------------|--------|---------|
| `gemma4:e2b` | 6 | 6 | 512 | 131072 |
| `gemma4:e4b` | 20 | 16 | 512 | 131072 |
| `gemma4:12b` | 320 | 8 | 1024 | 262144 |
| `gemma4:26b` | 200 | 10 | 1024 | 262144 |
| `gemma4:31b` | 800 | 40 | 1024 | 262144 |

`gemma4:e4b` at `8192` tokens with one request is `20 + 16 × 8192 / 1024 = 148` MiB of KV cache on top of the weights. The same model at `131072` tokens is `20 + 16 × 128 = 2068` MiB of KV cache. Below the window, scale the sliding-window cache by `context_tokens / window`.

`OLLAMA_KV_CACHE_TYPE=q8_0` multiplies that result by `1/2`. `q4_0` multiplies it by `1/4`.

That many MiB comes out of VRAM when the GPU has room after the weights. Otherwise it comes out of system RAM and counts against `mem_limit`.

---

### Trading Weight Precision for a Larger Model

Weight quantization is separate from the KV cache. Using fewer bits per weight shrinks the model file, which lets you fit a larger, smarter parameter size into the same RAM or VRAM budget.

By default, the standard tags (`gemma4:e2b` through `gemma4:31b`) already use 4-bit mixed precision (`Q4_K_M`). To pick a specific quantization variant, set `GEMMA_MODEL` on both services in `compose.lllm.override.yaml`:
- **26B MoE variants** use the `gemma4:26b-a4b-it-<quant>` naming pattern.
- **All other sizes** use `gemma4:<size>-it-<quant>`.

| Quantization | Best Used When | `e2b` | `e4b` | `12b` | `26b-a4b` | `31b` |
|--------------|----------------|------:|------:|------:|----------:|------:|
| **Default (`Q4_K_M`)** | **Start here.** Balanced 4-bit mixed precision where sensitive layers keep extra bits. | 4.6 GB | 6.6 GB | 8.0 GB | 18 GB | 20 GB |
| **QAT (`-it-qat`)** | **Tight on VRAM/RAM, or want faster tokens.** Google's Quantization-Aware Trained `Q4_0` weights; slightly smaller and faster to decode than `Q4_K_M` while preserving 4-bit quality. | 4.3 GB | 6.1 GB | 7.2 GB | 16 GB | 19 GB |
| **8-bit (`-it-q8_0`)** | **You have spare memory.** Very close to full precision, though moving 1.3×–1.7× more weight data slows down token generation. | 6.0 GB | 9.0 GB | 13 GB | 28 GB | 34 GB |
| **16-bit (`-it-bf16`)** | **Uncompressed reference quality.** Requires ~2× the memory of 8-bit; usually too large for local budgets without heavy disk swap. | 10 GB | 16 GB | 24 GB | 52 GB | 63 GB |

> **Rule of thumb: Upgrade the parameter size before upgrading bit precision.** A 4-bit model at the next size up (for example, `gemma4:12b-it-qat` at 7.2 GB) will give you noticeably better reasoning and code quality than an 8-bit version of a smaller model (`gemma4:e4b-it-q8_0` at 9.0 GB).

**Tags to avoid in this container:**
- **macOS / MLX-only tags (`-nvfp4`, `-mxfp8`, `-mlx`):** Ollama only serves these on native macOS Apple Silicon setups—they will fail to pull inside this Linux container, and their download sizes (`9.5 GB` for `e4b-nvfp4`) are actually larger than the default `Q4_K_M` tags.
- **Mobile 2-bit QAT (`wNa8o8`):** Google's sub-1 GB mobile checkpoints (`gemma-4-E2B-it-qat-mobile-*`) are built for LiteRT-LM and Transformers.js on phones and browsers, and are not available as Ollama tags.

---

### Trading Speed for Smarter Models (Disk Swap)

Can you run a larger, smarter model (like `e4b` or `26b`) if you don't have enough RAM?
**Yes, by using disk swap—but it will be significantly slower.**

#### How it works
When RAM fills up, your operating system moves inactive memory to an SSD swap file instead of crashing.
- **Good to know**: Disk swap allows a bigger model to load without getting killed by Docker.
- **Trade-off**: Reading model weights and token caches from disk is 10x–50x slower than RAM. Expect noticeable pauses between tokens.
- **Requirement**: You must have a fast SSD. Running LLM swap on a mechanical hard drive is practically unusable.

#### How to configure swap

1. **Keep `mem_limit` at your physical RAM budget**, and set `memswap_limit` to allow extra disk space.
   `memswap_limit` represents **RAM + Swap combined**:
   ```yaml
   services:
     local-llm:
       mem_limit: 12g        # Physical RAM cap
       memswap_limit: 20g    # 12g RAM + 8g disk swap
   ```

2. **Ensure your host OS has swap enabled**:
   - **Windows / WSL2**: In `%UserProfile%\.wslconfig`, add:
     ```ini
     [wsl2]
     swap=16GB
     ```
     Then restart WSL in PowerShell: `wsl --shutdown`.
   - **macOS (Docker Desktop)**: Go to **Settings → Resources → Advanced → Swap** (adjust slider).
   - **Linux**: Check existing swap with `swapon --show`. Create or expand a swapfile if needed.

3. **Choose a context window that matches how much memory you want to spend.**
   Longer context windows only increase the size of the KV cache; the model weights stay the same size. Setting `OLLAMA_KV_CACHE_TYPE=q8_0` cuts KV cache memory in half, and `q4_0` cuts it to a quarter—making 128K or 256K context windows possible even on an 8 GB or 16 GB machine. However, `q4_0` reduces recall accuracy over very long prompts, and if the KV cache spills into disk swap, every generated token will stall while reading from your SSD.

---

### Optimizing Around a Modest Development Machine (8 GB GPU + 16–32 GB RAM)

The configurations below are designed for a typical mid-range development machine where you can spare up to **7 GB of GPU VRAM** and **13 GB of system RAM** (`mem_limit: 13g` or lower, with `gpus: all` enabled).

If you aren't sure which one to pick, **start with Setup 1 (`gemma4:e4b-it-qat` at 32K context)**. It is the smartest model that runs 100% inside your GPU's VRAM, giving you instant responses and enough context for normal coding and chat. Switch to one of the other setups below only when your task demands a larger context window or deeper reasoning.

#### Quick Decision Guide

| Setup | Model & Context | Best For | What You Trade Off |
|-------|-----------------|----------|--------------------|
| **1. Daily Driver (Recommended)** | `e4b-it-qat` (32K) | Everyday coding, debugging, and responsive chat | Context fits a few files at a time, not a whole codebase |
| **2. Web Research Agent** | `12b-it-qat` (256K, `q8_0` cache) | Several page opens plus web searches, then structured notes or a simple decision | About 1.2 GB of cache sits in system RAM with a thin slice of the weights. Fine here, because this job is not interactive |
| **3. Fast Log & Diff Reader** | `e2b` (128K) | Summarizing huge logs, diffs, or docs at top speed | Weaker reasoning than E4B or 12B |
| **4. Long-Context Daily Driver** | `e4b-it-qat` (128K, `q4_0` cache) | Feeding a large document or many files into E4B at GPU speed | 4-bit KV cache (`q4_0`) can miss subtle details in very long prompts |
| **5. Stronger Code & Bug Solver** | `12b-it-qat` (8K) | Tricky bugs, complex refactoring, and multi-step logic | Slightly slower generation (0.2 GB of weights + cache spill into system RAM); smaller 8K window |
| **6. Whole-Module Analyst** | `12b-it-qat` (256K, `q4_0` cache) | Analyzing large multi-file features with 12B reasoning | Slight RAM offload slowdown + reduced long-prompt recall from `q4_0` cache |
| **7. Higher-Precision E4B** | `e4b-it-q8_0` (8K) | Nuanced writing or prompts where 4-bit E4B feels sloppy | Noticeably slower (2 GB of weights run in system RAM) without upgrading to a 12B model |
| **8. Heavy Reasoner (No Swap)** | `26b-a4b-it-qat` (8K or 256K) | Hard architectural problems where quality matters more than speed | Slow, steady generation (~9 GB of weights run in system RAM) |
| **9. Maximum Reasoning + Context (Light Swap)** | `31b-it-qat` (256K, `q4_0` cache) | Background analysis of massive prompts using the largest dense model | Token generation hitches as ~3 GB of weights page from SSD swap |
| **10. Uncompressed Ceiling (Heavy Swap)** | `26b-a4b-it-bf16` (8K) | One-off, walk-away batch prompts at full 16-bit precision | **10×–50× slower** (~34 GB streamed from SSD swap per token); unusable interactively |

---

#### 1. Daily Driver: `gemma4:e4b-it-qat` at 32K

- **Best for:** Everyday coding assistance, explaining functions, writing tests, and back-and-forth chat while working across a few files.
- **Why it works well:** Both the 6.1 GB model and the ~0.5 GB KV cache (~6.6 GB total) stay completely inside your 7 GB of VRAM. You get fast, 100% GPU-accelerated responses.
- **Tradeoff:** A 32K token window holds roughly 24,000 words—plenty for several source files, but not an entire repository.

```yaml
services:
  local-llm:
    mem_limit: 8g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:e4b-it-qat
      OLLAMA_CONTEXT_LENGTH: "32768"
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:e4b-it-qat
```

#### 2. Web Research Agent: `gemma4:12b-it-qat` at 256K (`q8_0` Cache)

- **Best for:** An agent that opens pages (for example with Chrome DevTools), runs web searches, then returns structured notes or makes a simple decision from what it found. Reply speed does not matter, and the session should not be capped at a handful of pages.
- **Why it works well:** 12B follows tool calls and a structured report more reliably than E4B. The window is the model's full 256K. A page snapshot is often 5–15K tokens, so that holds on the order of 10–20 pages plus search results and the tool transcript, instead of the 3–4 pages that fit in 64K. An 8-bit KV cache (`q8_0`) keeps the 256K buffer around 1.2 GB, which remembers earlier pages better than the 4-bit cache in Setup 6. The weight file is 7.2 GB, so about 0.2 GB of it sits in system RAM with that cache. `mem_limit: 8g` covers both. Tokens are slower than a model that fits entirely in VRAM, which is acceptable for a job you wait on.
- **Tradeoff:** Take text snapshots rather than screenshots so image tokens do not eat the window. Setup 6 is the same model and window with a `q4_0` cache (~0.6 GB) when you would rather spend that RAM elsewhere and can tolerate a coarser memory of long pages. If 12B still makes the wrong call, Setup 8 is the same kind of wait with a stronger model.

```yaml
services:
  local-llm:
    mem_limit: 8g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:12b-it-qat
      OLLAMA_CONTEXT_LENGTH: "262144"
      OLLAMA_KV_CACHE_TYPE: q8_0
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:12b-it-qat
```

#### 3. Fast Log & Diff Reader: `gemma4:e2b` at 128K

- **Best for:** Pasting massive build logs, stack traces, git diffs, or long documentation when you want an immediate summary without compressing the KV cache.
- **Why it works well:** The lightweight 4.6 GB model leaves enough room in VRAM for a full-precision (fp16) 128K KV cache (~0.8 GB, ~5.4 GB total). It is the fastest setup this machine can run.
- **Tradeoff:** E2B is the smallest model in the family and is noticeably less capable at complex logic or tricky code generation than E4B or 12B.

```yaml
services:
  local-llm:
    mem_limit: 8g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:e2b
      OLLAMA_CONTEXT_LENGTH: "131072"
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:e2b
```

#### 4. Long-Context Daily Driver: `gemma4:e4b-it-qat` at 128K (`q4_0` Cache)

- **Best for:** Reviewing a long document or a large set of files when E2B is too weak, but you still want fast GPU-only generation.
- **Why it works well:** Compressing the KV cache to 4-bit (`OLLAMA_KV_CACHE_TYPE: q4_0`) shrinks the 128K context buffer from ~2 GB down to ~0.5 GB, keeping the entire 6.6 GB footprint in VRAM.
- **Tradeoff:** A 4-bit KV cache loses some precision over very long contexts, so the model may occasionally overlook small details buried deep in a huge prompt. Use Setup 1 whenever 32K tokens is enough.

```yaml
services:
  local-llm:
    mem_limit: 8g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:e4b-it-qat
      OLLAMA_CONTEXT_LENGTH: "131072"
      OLLAMA_KV_CACHE_TYPE: q4_0
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:e4b-it-qat
```

#### 5. Stronger Code & Bug Solver: `gemma4:12b-it-qat` at 8K

- **Best for:** Debugging subtle issues, designing components, and multi-step coding tasks where E4B struggles and your prompt only needs a few files.
- **Why it works well:** Steps up to the 12B parameter tier (7.2 GB). Nearly the entire model fits in your 7 GB of VRAM, with just ~0.2 GB of weights and the ~0.4 GB KV cache spilling into system RAM.
- **Tradeoff:** Because the CPU has to process that small 0.2 GB slice of weights in system RAM on every token, generation is slightly slower than a 100% GPU setup, and the context window is kept to 8K tokens.

```yaml
services:
  local-llm:
    mem_limit: 6g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:12b-it-qat
      OLLAMA_CONTEXT_LENGTH: "8192"
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:12b-it-qat
```

#### 6. Whole-Module Analyst: `gemma4:12b-it-qat` at 256K (`q4_0` Cache)

- **Best for:** Feeding an entire module, a long specification, or dozens of files into the stronger 12B model at once.
- **Why it works well:** Pairs the 12B QAT model with a 4-bit KV cache (`q4_0`) so the full 256K context window takes only ~0.6 GB of system RAM alongside the 0.2 GB weight overflow.
- **Tradeoff:** Combines the slight speed penalty of reading 0.2 GB of weights from system RAM with the lower recall accuracy of a `q4_0` cache over massive prompts. *(Tip: If you notice the model forgetting details in long prompts, change `OLLAMA_KV_CACHE_TYPE` to `q8_0`—it uses ~1.2 GB of RAM and still fits comfortably inside `mem_limit: 6g`. Setup 2 is that setting, for a browsing session.)*

```yaml
services:
  local-llm:
    mem_limit: 6g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:12b-it-qat
      OLLAMA_CONTEXT_LENGTH: "262144"
      OLLAMA_KV_CACHE_TYPE: q4_0
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:12b-it-qat
```

#### 7. Higher-Precision E4B: `gemma4:e4b-it-q8_0` at 8K

- **Best for:** Tasks where you specifically want E4B's behavior without 4-bit quantization rounding (for example, strict formatting or nuanced prose over a short chat).
- **Why it works well:** Uses 8-bit weights (9.0 GB) so output closely tracks the uncompressed E4B model.
- **Tradeoff:** 2 GB of weights spill into system RAM and must be read by the CPU on every token, making it noticeably slower than 4-bit E4B without giving you a larger model. For harder coding or reasoning tasks, **Setup 5 (`12b-it-qat`)** is almost always a better use of your memory.

```yaml
services:
  local-llm:
    mem_limit: 8g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:e4b-it-q8_0
      OLLAMA_CONTEXT_LENGTH: "8192"
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:e4b-it-q8_0
```

#### 8. Heavy Reasoner (No Disk Swap) (Sam's choice): `gemma4:26b-a4b-it-qat` at 8K or 256K

- **Best for:** Complex architecture reviews or hard reasoning problems where 12B isn't enough and you don't mind waiting a bit for a much smarter answer.
- **Why it works well:** The 26B Mixture-of-Experts model (16 GB) fits across your 7 GB of VRAM and 13 GB of system RAM without touching disk swap, and only activates 3.8B parameters per token.
- **Tradeoff:** Because ~9 GB of the model lives in system RAM, token generation drops to a slower, deliberate pace. The YAML below configures the 256K window using a `q4_0` cache (~0.7 GB); for a sharper 8K window at full cache precision, change `OLLAMA_CONTEXT_LENGTH` to `"8192"` and remove `OLLAMA_KV_CACHE_TYPE`.

```yaml
services:
  local-llm:
    mem_limit: 13g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:26b-a4b-it-qat
      OLLAMA_CONTEXT_LENGTH: "262144"
      OLLAMA_KV_CACHE_TYPE: q4_0
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:26b-a4b-it-qat
```

#### 9. Extreme: Maximum Reasoning + 256K Context (`gemma4:31b-it-qat` with Light SSD Swap)

- **Best for:** Deep, background analysis across a massive 256K prompt using the largest 31B dense model—when you can submit a prompt, switch tasks, and come back a few minutes later.
- **Why it works well:** Fits a 19 GB dense model and a 256K `q4_0` KV cache (~2.7 GB) on a modest machine by letting the last ~3 GB overflow into host SSD swap (`memswap_limit: 20g`).
- **Tradeoff:** Every token has to page those overflow weights from your SSD, causing visible pauses ("hitching") during generation. Make sure your host has at least 7 GB of fast SSD swap configured (see [How to configure swap](#how-to-configure-swap)).

```yaml
services:
  local-llm:
    mem_limit: 13g
    memswap_limit: 20g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:31b-it-qat
      OLLAMA_CONTEXT_LENGTH: "262144"
      OLLAMA_KV_CACHE_TYPE: q4_0
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:31b-it-qat
```

#### 10. Extreme (10×–50× Slower): Uncompressed 26B (`gemma4:26b-a4b-it-bf16` with Heavy SSD Swap)

- **Best for:** Rare, one-off verification runs where you want zero quantization loss on the 26B model and are willing to walk away while it runs.
- **Why it works well:** Loads the full 52 GB `bf16` checkpoint by combining 7 GB of VRAM, 13 GB of container RAM, and ~35 GB of host SSD swap (`memswap_limit: 48g`).
- **Tradeoff:** **10×–50× slower than RAM.** Roughly 34 GB of model weights must be streamed off your SSD for every generated token, and heavy swap traffic will wear on your drive over time. Keep context at `8192` so the KV cache doesn't add even more disk I/O. *(For the 63 GB `gemma4:31b-it-bf16` model, raise `memswap_limit` to `60g` and ensure ~47 GB of host swap.)*

```yaml
services:
  local-llm:
    mem_limit: 13g
    memswap_limit: 48g
    gpus: all
    environment:
      GEMMA_MODEL: gemma4:26b-a4b-it-bf16
      OLLAMA_CONTEXT_LENGTH: "8192"
  devcontainer:
    environment:
      GEMMA_MODEL: gemma4:26b-a4b-it-bf16
```

---

## Testing & Verifying Your Setup

After editing `compose.lllm.override.yaml`, apply changes by rebuilding or restarting:
```sh
devcontainer up
```

Inside the devcontainer terminal:
1. **Start a quick chat**:
   ```sh
   gemma
   ```
2. **Check model placement and allocated context**:
   Open a second terminal and run:
   ```sh
   ollama ps
   ```
   Look at the output:
   - `PROCESSOR: 100% GPU`: Running completely on your graphics card (fastest).
   - `PROCESSOR: 100% CPU`: Running in system RAM (normal for Mac / non-GPU).
   - `PROCESSOR: 40%/60% CPU/GPU`: Hybrid mode offloading layers.
   - `CONTEXT`: Shows the token window currently active (e.g. `8192`).

---

## Free Disk Space Checklist

Before downloading a model, ensure your drive has enough free storage:
- **Docker image**: ~3 GB of disk
- **Weight-file download** (plain `Q4_K_M` tag, what this container stores):
  - `gemma4:e2b`: 4.6 GB of weights
  - `gemma4:e4b`: 6.6 GB of weights
  - `gemma4:12b`: 8.0 GB of weights
  - `gemma4:26b`: 18 GB of weights
  - `gemma4:31b`: 20 GB of weights
  - QAT tags (`-it-qat`) weight-file downloads: 4.3 / 6.1 / 7.2 / 16 / 19 GB for e2b, e4b, 12b, 26b-a4b, and 31b. `bf16` weight-file downloads are 10 / 16 / 24 / 52 / 63 GB for those same parameter sizes.
- **Buffer / temp headroom**: Keep at least **10 GB of free disk space** so downloads don't fail midway.
