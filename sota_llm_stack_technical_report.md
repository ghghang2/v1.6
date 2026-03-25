# The SOTA LLM Stack: Architecture, Systems, and Future Directions
## A First-Principles Technical Reference

*Compiled March 2026. Synthesizes: Kimi Attention Residuals (2026), Anthropic Biology of an LLM (2025), NVIDIA GTC 2026 (SemiAnalysis), RYS neuroanatomy (2026), and related primary sources.*

*Target audience: Engineering students with undergraduate-level linear algebra and probability. Assumes familiarity with neural networks but no prior LLM-specific knowledge.*

---

## Table of Contents

1. [The Canonical Transformer: First Principles](#1-the-canonical-transformer-first-principles)
2. [Architecture Variants: State of the Art Compared](#2-architecture-variants-state-of-the-art-compared)
3. [Deep Dives: P/D Split, AFD, Attention, FFN, and Hardware Co-Design](#3-deep-dives-pd-split-afd-attention-ffn-and-hardware-co-design)
4. [Forward-Looking R&D: Grounded Technical Speculation](#4-forward-looking-rd-grounded-technical-speculation)
5. [Notes and References](#5-notes-and-references)

### Document Structure and Reading Guide

This document is organized to build understanding progressively:

- **Section 1** establishes the canonical transformer architecture from first principles. All subsequent sections build on these foundations.
- **Section 2** surveys state-of-the-art variants, explaining how each addresses limitations identified in Section 1.
- **Section 3** dives into systems-level considerations, connecting architecture choices to hardware constraints.
- **Section 4** explores emerging research directions grounded in the principles established earlier.

**Reading recommendations**:
- *New to transformers*: Read Section 1 completely before proceeding
- *Familiar with transformers*: Skim Section 1, focus on Sections 2-3
- *Systems-focused*: Sections 1.8, 2.1, 3.2-3.8
- *Architecture research*: Sections 1.4-1.7, 2.3-2.6, 4.1-4.6

---

## 1. The Canonical Transformer: First Principles

### 1.1 The Information Flow: A Token's Journey

A transformer processes a sequence of discrete tokens. Each token begins as an integer ID produced by a tokenizer (typically byte-pair encoding, BPE). Understanding the full pipeline requires tracking both the shape and the semantics of activations at each stage.

**Why transformers?** To appreciate the transformer architecture, we need to understand what problem it solves. Earlier sequence models like RNNs and LSTMs processed data sequentially, computing hidden states one token at a time:

```
RNN: h_t = f(h_{t-1}, x_t)  # Sequential, O(T) latency
```

This sequential dependency prevented parallelization during training. The transformer's key innovation is **attention**, which computes relationships between all token pairs simultaneously, enabling parallel computation and capturing long-range dependencies more effectively [^vaswani2017].

**Key insight**: Attention replaces recurrence with direct token-to-token communication, enabling models to learn relationships across arbitrary distances in the sequence.

#### Tokenization Primer

Before diving into the transformer, let's understand how text becomes numbers. Tokenization converts raw text into integer sequences that the model can process.

**Byte-Pair Encoding (BPE)** algorithm:

A transformer processes a sequence of discrete tokens. Each token begins as an integer ID produced by a tokenizer (typically byte-pair encoding, BPE). Understanding the full pipeline requires tracking both the shape and the semantics of activations at each stage.

```
Raw text: "the capital of Texas is"
   ↓ BPE tokenizer
Token IDs: [1820, 6864, 315, 8421, 374]  (shape: [T=5])
   ↓ Embedding lookup  E ∈ ℝ^{V×d}
Token embeddings: [T=5, d=4096]
   + Positional encoding (RoPE): [T=5, d=4096]
   ↓ L transformer layers
   ↓ Final layer norm
   ↓ Unembedding  W_U ∈ ℝ^{d×V}
Logits: [T=5, V=128256]
   ↓ Softmax (or sampling)
Next token: "Austin"
```

**Vocabulary size V** is typically 32k–200k. **Hidden dimension d** (also called `d_model`) ranges from 2048 (small) to 14336 (Llama-3 70B) to ~7168 (DeepSeek V3). The embedding matrix E doubles as the unembedding matrix in most modern models (weight tying), saving V×d parameters.

**Why weight tying?** The embedding and unembedding matrices learn related representations: embeddings map tokens to semantic vectors, while unembedding maps vectors back to token probabilities. Sharing weights constrains the model to learn consistent representations in both directions, improving generalization especially for rare tokens [^press2020].

#### Embedding Dimension Selection

The hidden dimension d determines the model's capacity to represent information. A rule of thumb from transformer theory:

```
d ≈ √(total_params / (L × constant))
```

Where L is the number of layers. For a 70B model with 80 layers, d ≈ 8192 provides sufficient capacity without excessive memory overhead.

**Exercise**: Calculate the embedding dimension for a 13B model with 40 layers, assuming similar parameter distribution.

*Solution*: d ≈ √(13B / (40 × 6)) ≈ √54M ≈ 7350 (practically rounded to 8192 for power-of-2 memory alignment).

### 1.2 Positional Encoding: RoPE in Detail

**Why positional encoding?** Unlike RNNs that naturally encode position through sequential processing, transformers process all tokens in parallel. We must inject position information to enable the model to distinguish token order. Early approaches used absolute positions, but these fail to generalize to longer sequences during inference.

**Evolution of positional encoding**:
1. *Absolute positional encoding* (original transformer): Learnable embeddings added to token embeddings
2. *Sinusoidal encoding* (original transformer): Fixed sinusoidal functions with different frequencies
3. *Relative positional encoding* (T5, etc.): Explicit relative position biases
4. *Rotary embeddings (RoPE)* (current standard): Position-dependent rotation in 2D subspaces

The key insight behind RoPE is that **attention should depend on relative position** (how far apart tokens are) rather than absolute position (where tokens are in the sequence). This enables better generalization to longer contexts.

#### Mathematical Foundation of RoPE

RoPE encodes position by rotating query and key vectors in 2D subspaces of the hidden dimension. The rotation angle depends on the token's position, but crucially, attention scores depend only on the *difference* between positions.

**Complex number interpretation**: RoPE can be understood as multiplying complex numbers. If we represent q and k as complex numbers with phase encoding position:

```
q_m = q · e^(iθm), k_n = k · e^(iθn)
q_m · k_n* = |q||k| · e^(iθ(m-n))  # Only depends on m-n
```

This is the mathematical foundation for why RoPE naturally encodes relative position.

Modern models use **Rotary Position Embeddings (RoPE)** rather than learned absolute or sinusoidal positions. RoPE encodes position by rotating query and key vectors in 2D subspaces of the hidden dimension:

```
For head dimension d_h, define rotation matrix R(θ, m) for position m:
  q_m = R(θ, m) · q     k_n = R(θ, n) · k
  
Attention score: q_m · k_n = q · R(θ, m-n) · k  (only relative position m-n matters)

RoPE rotation for dimension pair (2i, 2i+1):
  [cos(m·θ_i)  -sin(m·θ_i)] [q_{2i}  ]
  [sin(m·θ_i)   cos(m·θ_i)] [q_{2i+1}]

where θ_i = base^{-2i/d_h}, base typically 10000 (extended to 500000+ for long context)
```

RoPE is applied only to the Q and K projections, not V. This means value information is position-agnostic — a critical property exploited by MLA (see §2.2). The base frequency controls the **context length extrapolation**: higher base → slower rotation → longer effective context before aliasing.

#### Context Length Extrapolation

A critical challenge with RoPE is extrapolating to context lengths beyond training. The rotation frequency θ_i determines how quickly the attention pattern repeats. For a base of 10000 and d_h=128:

```
Period at dimension i: P_i = 2π / θ_i = 2π · base^(2i/d_h)
```

Higher dimensions have longer periods, enabling the model to encode both short-range and long-range dependencies. **NTK-aware RoPE** (Su et al., 2022) interpolates frequencies to enable training on shorter contexts and inference on longer ones.

**Exercise**: Calculate the period at the lowest frequency dimension (i=0) for base=10000 and d_h=128.

*Solution*: θ_0 = 10000^0 = 1, so P_0 = 2π ≈ 6.28. This means the lowest frequency dimension completes a full rotation every 6.28 tokens.

### 1.3 The Attention Mechanism: Scaled Dot-Product

**What does attention actually compute?** At its core, attention answers: "Given the current token, which other tokens in the sequence are most relevant?" The mechanism computes a weighted sum of value vectors, where weights are determined by compatibility between query and key vectors.

**Intuition through an example**: Consider the sentence "The animal didn't cross the street because it was too fat." When processing "it", the attention mechanism should attend strongly to "animal" (the antecedent) rather than "street". This is how transformers learn **coreference resolution**.

#### The Attention Computation Step-by-Step

1. **Query-Key compatibility**: Q·K^T computes a T×T matrix where entry (i,j) measures how much token i should attend to token j
2. **Scaling**: Division by √d_h prevents dot products from growing too large, which would push softmax into regions with tiny gradients
3. **Masking**: Causal mask zeros out future positions (for autoregressive models)
4. **Softmax**: Converts scores to probabilities (weights summing to 1)
5. **Value aggregation**: Weighted sum of V produces the attended representation

**Why √d_h scaling?** Without scaling, dot products grow as √d_h in magnitude (by concentration of measure). This pushes softmax into saturation regions where gradients vanish. The scaling keeps activations in a regime where gradients flow effectively [^vaswani2017].

#### Multi-Head Attention: Why Multiple Heads?

Single-head attention learns a single attention pattern. Multi-head attention allows the model to learn different attention patterns in parallel:
- Some heads attend to syntactic dependencies (subject-verb agreement)
- Some heads attend to semantic relationships (coreference)
- Some heads attend to positional patterns (copying, counting)

This **specialization** is analogous to convolutional filters learning different edge orientations.

For a single attention head with head dimension `d_h = d / H` (H = number of heads):

```
Given input X ∈ ℝ^{T×d}:

Q = X · W_Q    W_Q ∈ ℝ^{d×d_h}
K = X · W_K    W_K ∈ ℝ^{d×d_k}   (d_k may differ from d_h in MQA/GQA/MLA)
V = X · W_V    W_V ∈ ℝ^{d×d_v}

Attention(Q, K, V) = softmax(QK^T / √d_h) · V

Output ∈ ℝ^{T×d_h}, then concatenated across H heads and projected:
  MultiHead = Concat(head_1, ..., head_H) · W_O    W_O ∈ ℝ^{(H·d_h)×d}
```

**Computational complexity**: O(T²·d) for the attention matrix. For T=128k tokens and d=4096, this is ~68 billion operations per layer — the primary bottleneck for long-context prefill.

#### Attention Pattern Visualization

Attention patterns reveal what the model has learned. Common patterns include:

| Pattern Type | Description | Example |
|-------------|-------------|---------|
| **Copy** | Attends to previous identical token | "the ... the" |
| **Previous** | Attends to immediately preceding token | Sequential processing |
| **First** | Attends to first token in sequence | Context anchoring |
| **Current** | Self-attention (diagonal) | Token self-representation |
| **Structural** | Attends to syntactic dependencies | Subject-verb agreement |

Mechanistic interpretability research has shown that different heads specialize in different patterns, with some heads consistently learning copy patterns across training runs [^herrmann2022].

**Exercise**: For a sentence of length T=100, calculate the number of attention scores computed per layer with H=12 heads.

*Solution*: T² = 10,000 scores per head × 12 heads = 120,000 scores per layer.

**Memory complexity**: The KV cache stores K and V for all previous tokens. For a single layer, single token being generated with context length T:
```
KV cache size per layer = 2 × T × d_k × dtype_bytes
Example (T=8192, d_k=128, H_kv=8, FP16=2B):
  = 2 × 8192 × 128 × 8 × 2 = 33.5 MB per layer
  × 60 layers = ~2 GB total for a 70B model at 8k context
  × 128k context = ~32 GB — exceeding single GPU VRAM
```

This is why KV cache management is one of the most active areas of systems research.

#### Why KV Cache Dominates Memory

During inference, we generate tokens one at a time. To compute attention for the new token, we need all previous K and V vectors. This creates a memory bottleneck that grows linearly with context length.

**Memory breakdown for Llama-70B at 32k context**:

| Component | Size | Percentage |
|-----------|------|------------|
| Model weights | 140 GB (FP16) | 70% |
| KV cache | 60 GB | 30% |
| **Total** | **200 GB** | **100%** |

This explains why inference at long context requires multiple GPUs or specialized memory management (see §3.5).

**Exercise**: Calculate KV cache size for a 13B model at 128k context with d_k=128, H_kv=16, FP16.

*Solution*: Per layer: 2 × 128k × 128 × 16 × 2B = 1024 MB = 1 GB. For 40 layers: 40 GB total.

**Key insight**: KV cache is the primary memory bottleneck for long-context inference, not model weights. This motivates techniques like MLA, quantization, and KV cache compression.

**Connection to Section 2.1**: DeepSeek V3's MLA directly addresses this bottleneck by compressing the KV cache.

### 1.4 The Residual Stream: The Information Highway

**Why residual connections?** In deep networks, information must flow from input to output through many layers. Without residual connections, each layer must learn to preserve the input while adding new information — an increasingly difficult task as depth grows. Residual connections solve this by providing a direct path for information to flow through the network.

**The residual stream as information highway**: Think of the residual stream h as a shared memory buffer that all layers read from and write to. Each layer computes a transformation f(h) and adds it back to h. This means:

```
h_L = h_0 + Σ_{i=1}^{L} f_i(h_i)
```

Every layer's output is directly visible to all subsequent layers. This is fundamentally different from traditional deep learning where information flows sequentially through layers.

#### Mechanistic Interpretability Perspective

The residual stream is where the model's "thought process" unfolds. Mechanistic interpretability research has revealed that:

1. **Different positions in the stream encode different information**: Early layers encode raw token features, middle layers encode syntactic structure, later layers encode semantic meaning and task-specific reasoning.
2. **Attention heads read and write specific information**: Some heads copy information from earlier positions, others aggregate information across the sequence.
3. **FFNs compute discrete transformations**: FFNs often implement "if-then" logic, activating only for specific input patterns.

**Example from mechanistic interpretability**: In a model predicting the next token in "Paris is the capital of ____", researchers have traced how:
- Layer 1-5: Encode "Paris" as a location entity
- Layer 6-15: Recognize the "capital of" pattern
- Layer 16-25: Retrieve country information
- Layer 26-30: Generate "France"

This decomposition reveals that transformers implement **circuit-like computation** where different layers specialize in different subtasks [^anthropic2022].

#### PreNorm vs PostNorm: The Training Stability Tradeoff

The placement of normalization relative to the residual connection has profound implications for training dynamics.

**PreNorm** (normalization before residual):
```
h = h + LayerNorm(h) + f(h)
```
Advantages: Stable gradients, easier training  
Disadvantages: Information dilution (see §2.3)

**PostNorm** (normalization after residual):
```
h = LayerNorm(h + f(h))
```
Advantages: Better information flow  
Disadvantages: Training instability, harder to optimize

**The dilution problem**: Under PreNorm, the magnitude of h grows as O(L) because each layer adds its output to the cumulative sum. This means the normalized input to layer l has signal-to-noise ratio O(1/l), causing later layers to receive increasingly weak signals [^kimi2026].

**Exercise**: If each layer adds a transformation of magnitude 1, what is the magnitude of h after L=30 layers?

*Solution*: ∥h∥ ≈ √L = √30 ≈ 5.5 (assuming orthogonal transformations). In practice, the growth is more like O(L) due to correlated updates.

**Connection to Section 2.3**: Kimi's Attention Residuals architecture directly addresses the PreNorm dilution problem.
The residual connection is the architectural innovation that made deep transformers trainable. The update rule:

```
h_l = h_{l-1} + f_l(h_{l-1})
```

Unrolled to depth L:
```
h_L = h_1 + Σ_{i=1}^{L-1} f_i(h_i)
```

This means **every layer output accumulates uniformly** into the final representation — a fact with profound implications. The **PreNorm** variant (now standard) applies layer norm before each sublayer:

```
h' = h + Attention(LayerNorm(h))
h'' = h' + FFN(LayerNorm(h'))
```

**PreNorm dilution** (identified formally in SiameseNorm [27] and quantified in AttnRes [Kimi2026]): since each sublayer adds to an ever-growing residual stream, the relative contribution of any single layer decreases as ‖h_l‖ grows as O(L). Deeper layers must learn increasingly large outputs to remain influential. Empirically, this means a significant fraction of middle layers can be removed with minimal performance loss — validating the RYS functional anatomy hypothesis.

The standard residual's depth mixing matrix M is:
```
M ∈ ℝ^{L×L}, where M_{i→l} = 1 for all i < l  (all-ones lower triangular)
```
This is the most primitive possible aggregation: uniform, input-independent, with no mechanism for selective retrieval of earlier representations.

### 1.5 The FFN/MLP: Pattern Storage

The feed-forward network processes each token position independently:

```
FFN(x) = W_2 · σ(W_1 · x)    (original, ReLU activation)

Modern SwiGLU variant (used in LLaMA, Qwen, DeepSeek):
FFN(x) = (SiLU(W_gate · x) ⊙ W_up · x) · W_down

where:
  W_gate ∈ ℝ^{d×d_ff}
  W_up   ∈ ℝ^{d×d_ff}
  W_down ∈ ℝ^{d_ff×d}
  d_ff typically 4d (dense) or 8/3·d (SwiGLU corrected for parameter parity)
```

The FFN has been interpreted as a **key-value memory** (Geva et al., 2021 [^geva2021]): W_1 rows are "keys" that match input patterns, and W_2 columns are corresponding "values" that modify the residual stream. Each neuron fires when its key pattern is present in the input, adding the corresponding value. This is the mechanistic basis for the claim that FFN layers store factual associations — confirmed by the Anthropic biology paper's circuit tracing, which identified FFN features representing specific geographical, linguistic, and conceptual associations.

**Parameter count breakdown** for a typical 70B dense model (d=8192, d_ff=28672, H=64, L=80):
```
Embedding:            V × d = 128256 × 8192 ≈ 1.05B
Attention (per layer): d×(d_k + d_v + H·d_h + d) = 4 × d² ≈ 268M per layer
FFN (per layer):       d×d_ff×3 (SwiGLU) ≈ 603M per layer
Total attention:       268M × 80 ≈ 21.4B
Total FFN:             603M × 80 ≈ 48.2B
Total ≈ 70.7B ✓
```

FFN is ~68% of total parameters in a dense transformer — the dominant component.

### 1.6 Layer Normalization: Stabilizing Training

```
LayerNorm(x) = (x - μ) / (σ + ε) × γ + β    [original, over d dimensions]
RMSNorm(x) = x / RMS(x) × γ    where RMS(x) = √(1/d · Σ x_i²)
```

RMSNorm (used in LLaMA, DeepSeek, Qwen) removes the mean subtraction, saving ~30% of compute while maintaining numerical stability. It also eliminates the bias term β, reducing parameters.

### 1.7 Mixture-of-Experts: Conditional Computation

MoE replaces the single FFN with N_e experts {E_1, ..., E_{N_e}}, of which only K are activated per token:

```
Router: s = Softmax(W_r · x)  ∈ ℝ^{N_e}
Top-K selection: select indices I = argtopk(s, K)
MoE output: Σ_{i∈I} s_i / Σ_{j∈I} s_j · E_i(x)   (normalized routing weights)
```

**The key MoE arithmetic**:
```
Dense FFN active params per token: d_ff × d (one expert = all parameters)
MoE active params per token:       K × (d_ff_expert × d)
  where d_ff_expert = d_ff_dense / (N_e/K)  (to match FLOPs to dense baseline)

DeepSeek V3 example:
  N_e = 256 routed experts + 1 shared
  K = 8 activated per token
  d_ff_expert ≈ 2048
  Active params per token: 8 × 2048 × 7168 ≈ 117M (vs ~20B for full dense model)
  Total params: 685B
  Active params: ~37B  (ratio = 37/685 ≈ 5.4% of weights active per token)
```

This creates the MoE inference paradox: the model has 685B parameters but only reads ~37B from memory per decode step. The bandwidth math therefore uses 37GB (not 685GB) as the "active weight bytes" term in throughput calculations. Expert **load balancing** (ensuring all experts receive roughly equal tokens) is critical — DeepSeek V3 achieves this without auxiliary losses using a bias term on routing logits.

### 1.8 The Forward Pass: Putting It Together

```
Algorithm: Transformer Forward Pass (decoder-only, causal)

Input: token IDs x[1..T]
Output: logits L[1..T, V]

1. h = Embedding(x) + PositionalEncoding(x)    # [T, d]

2. For l = 1 to L:
   a. h_attn = RMSNorm(h)
   b. Q, K, V = h_attn · W_Q, h_attn · W_K, h_attn · W_V
   c. Apply RoPE to Q, K
   d. Append K, V to KV cache (inference only)
   e. A = softmax(Q · K^T / √d_h + causal_mask) · V   # [T, d]
   f. h = h + A · W_O                                   # residual connection
   
   g. h_ffn = RMSNorm(h)
   h. If MoE: route h_ffn to K experts, aggregate
      Else:   h = h + FFN(h_ffn)
   i. h = h + FFN_output                                # residual connection

3. h = RMSNorm(h)
4. L = h · W_U    # [T, V], unembedding

5. During inference: sample next token from L[-1, :]
```

---

## 2. Architecture Variants: State of the Art Compared

### 2.1 DeepSeek V3 / R1: The Efficiency Benchmark

DeepSeek V3 (685B total / 37B active) represents the current open-weight Pareto frontier on the quality-vs-cost curve. Its key innovations:

**Multi-head Latent Attention (MLA)**:

Standard MHA maintains a KV cache of size `2 × T × H × d_h` per layer. For large T, this dominates memory. MLA compresses this:

```
Standard MHA KV cache per layer:
  K ∈ ℝ^{T × H × d_h}   (e.g., T=128k, H=128, d_h=128 → 2GB per layer)
  V ∈ ℝ^{T × H × d_h}

MLA: store compressed latent c^{KV} ∈ ℝ^{T × d_c}  (d_c << H × d_h)
  During generation:
  K = c^{KV} · W_UK + RoPE(c^{KV} · W_UK^R)   # decompress K (includes RoPE component)
  V = c^{KV} · W_UV                              # decompress V

KV cache reduction:
  Standard: 2 × T × 128 × 128 × 2B = 65.5 MB/layer at 128k tokens
  MLA:      T × d_c × 2B           = 0.5 MB/layer at 128k (d_c=512)
  Reduction: ~130×
```

The key insight: V has no positional content, so it compresses well. K's positional component is separated into a tiny RoPE-encoded auxiliary cache. This is a direct application of the anatomical insight that position and content are separable in the attention mechanism.

**Auxiliary-Loss-Free Load Balancing**:

Traditional MoE adds an auxiliary loss L_aux = N_e · Σ_i f_i · P_i to penalize unequal expert utilization. DeepSeek V3 instead maintains a per-expert bias b_i updated each training step:

```
Routing logit: s_i = (W_r · x)_i + b_i
Top-K selected from s_i, but routing weight uses s_i (without b_i)
After each batch:
  b_i += α if expert_i overloaded
  b_i -= α if expert_i underloaded
```

This separates routing (uses biased logits for balance) from weighting (uses unbiased logits for quality), eliminating the quality-balance tradeoff.

**Multi-Token Prediction (MTP)**:

DeepSeek V3 adds K auxiliary heads that predict tokens t+2, t+3, ..., t+K+1 given representation at position t:

```
Standard: loss = -log P(t+1 | t, t-1, ..., 1)
MTP:      loss = -log P(t+1|...) - λ Σ_{k=2}^{K+1} -log P(t+k|...)

Benefits:
1. Training: K+1× data efficiency per token
2. Inference: MTP heads become draft model for speculative decoding
   Acceptance rate ~1.5-2× tokens per decode step
```

### 2.2 Qwen3.5: The Open-Weight MoE Spectrum

Alibaba's Qwen3.5 family provides a continuous tradeoff spectrum, making it the most practically useful open-weight family for deployment analysis:

| Model | Total params | Active | GPQA | SWE-bench | Min VRAM |
|-------|-------------|--------|------|-----------|---------|
| 9B dense | 9B | 9B | 81.7% | — | 18 GB |
| 27B dense | 27B | 27B | 85.5% | 72.4% | 54 GB |
| 35B-A3B MoE | 35B | 3B | 84.2% | 69.2% | ~24 GB* |
| 122B-A10B MoE | 122B | 10B | 86.6% | 72.0% | ~64 GB† |

*All weights must be loaded even though only 3B active; 35B × 1B/param = ~35 GB in FP16, ~17.5 GB in Q4
†122B × 0.5 bytes/param (Q4) ≈ 61 GB — borderline for M3 Ultra 192GB

**Thinking mode** is architecturally significant: the same weights produce qualitatively different outputs based on whether the `<think>` token triggers extended chain-of-thought. This is not a different model — it's the same weights with a different sampling regime that forces explicit intermediate reasoning tokens. The benchmark gap between thinking and non-thinking mode (AIME 2025: ~40% → ~91% for Qwen3.5-122B) is the quantitative value of extended reasoning cortex utilization.

### 2.3 Kimi Attention Residuals: Repairing the Depth Highway

The AttnRes paper [Kimi2026] addresses the **PreNorm dilution** problem with a theoretically motivated architectural replacement.

**The core problem, stated precisely**:

Under PreNorm, each layer l receives the accumulated sum:
```
h_l = h_1 + Σ_{i=1}^{l-1} f_i(h_i)
```

Since ‖h_l‖ = O(l) (grows linearly with depth), the normalized input to layer l is:
```
LN(h_l) = h_l / ‖h_l‖    (RMSNorm approximation)
```

The layer l's output contribution to h_{l+1} must overcome the O(l) magnitude of h_l to remain influential. This forces deeper layers to learn large-magnitude outputs — and explains why layers can be pruned: many simply learned to output near-zero to avoid interfering with the accumulated signal.

**AttnRes solution**: Replace the fixed uniform aggregation with learned softmax attention over depth:

```
Standard residual:  h_l = Σ_{i=0}^{l-1} v_i               (M_{i→l} = 1 always)
Full AttnRes:       h_l = Σ_{i=0}^{l-1} α_{i→l} · v_i    (M_{i→l} = α_{i→l} via softmax)

where:
  v_0 = h_1  (token embedding)
  v_i = f_i(h_i) for i ≥ 1  (layer output)
  α_{i→l} = softmax_i( w_l^T · RMSNorm(v_i) )
  w_l ∈ ℝ^d is a learned pseudo-query (one vector per layer, input-independent)
```

The pseudo-query being **input-independent** is a deliberate design choice: it makes attention weights at layer l computable in parallel for all layers in a block, enabling the two-phase batched inference schedule (see §3.6). An input-dependent query (projecting from h_l) improves loss by 0.006 further (1.737 → 1.731) but requires sequential memory access during decoding.

**Block AttnRes — the practical variant**:

Full AttnRes requires O(Ld) memory to retain all layer outputs for cross-layer aggregation. At L=128, d=7168, FP16: 128 × 7168 × 2 = 1.84 GB per token (infeasible for batch inference). Block AttnRes compresses this:

```
Partition L layers into N blocks of S = L/N layers each.
Within block n:
  b_n = Σ_{j ∈ B_n} f_j(h_j)   (sum, not attention)
  
Inter-block attention at layer l in block n:
  V = [b_0, b_1, ..., b_{n-1}, b_n^{partial}]   (N+1 vectors)
  h_l = Σ_{i=0}^{n} α_{i→l} · V_i

Memory: N × d × 2B (e.g., N=8, d=7168: 229 KB per token — 8000× reduction)
```

**Quantitative results from the paper**:

```
Scaling law experiment (5 model sizes, Table 2):
  Baseline:      L = 1.891 × C^{-0.057}
  Block AttnRes: L = 1.870 × C^{-0.058}
  
At 5.6 PFLOP/s-days:
  Baseline loss:      1.714
  Block AttnRes loss: 1.692
  → Equivalent to 1.25× more compute at no extra cost

48B model (1.4T token training), downstream results:
  GPQA-Diamond: 36.9 → 44.4  (+7.5 points)
  Math:         53.5 → 57.1  (+3.6 points)
  HumanEval:    59.1 → 62.2  (+3.1 points)
  MMLU:         73.5 → 74.6  (+1.1 points)
```

The improvement is largest on multi-step reasoning tasks (+7.5 GPQA) and smallest on knowledge recall (+1.1 MMLU) — consistent with the hypothesis that richer depth-wise information flow specifically benefits **compositional computation** where later layers need to selectively retrieve representations from earlier layers.

**The learned attention patterns** (Figure 8 of the paper) reveal:
- **Diagonal dominance**: each layer primarily attends to its immediate predecessor (local residual path preserved)
- **Embedding persistence**: h_1 (token embedding) retains significant weight throughout, especially for attention layers
- **Attention layers vs MLP layers differ**: pre-attention inputs show broader receptive fields, pre-MLP inputs show sharper local focus

This is the smoking gun that confirms the functional anatomy hypothesis independently: **attention layers are long-range integrators (routing information across depth), while MLP layers are local processors (operating on the current representation)**. This is the architectural correlate of the NVIDIA AFD insight — and it emerged from studying residual weights, not from hardware analysis.

**Architecture shift induced by AttnRes**:

AttnRes shifts the optimal depth-width tradeoff. Under fixed compute and parameter budget:
```
Baseline optimal:  d_model/L_b ≈ 60  (wider, shallower)
AttnRes optimal:   d_model/L_b ≈ 45  (narrower, deeper)
```

This is significant: if AttnRes becomes the standard residual connection, the optimal transformer architecture changes shape. Models should be deeper and narrower, relying on AttnRes to efficiently route information across the increased depth. The RYS experiment's finding (duplicating middle layers improves performance) is the empirical pre-training-free validation of the same underlying truth.

### 2.4 Claude 3.5 Haiku: Mechanistic Interpretability as Architecture Archaeology

Claude 3.5 Haiku (from the Anthropic biology paper [Anthropic2025]) is the only model for which we have circuit-level mechanistic understanding. Key architectural findings:

**Multi-step reasoning circuits**: For the prompt "the capital of the state containing Dallas is", the attribution graph reveals:
```
[Dallas tokens] → [Texas features] → [say Austin]
[capital tokens] → [say a capital]  ↗
```
With a shortcut edge Dallas → Austin. Two parallel pathways, both contributing. Inhibiting "Texas" features causes the model to output other state capitals; swapping "Texas" for "California" features outputs "Sacramento." These are **not** soft weights — they are discrete, manipulable information units.

**Planning circuits**: Before writing the rhyming word at the end of a poem line, the model activates features representing candidate end-words ~10-15 layers in advance. This is forward planning in the literal sense: the model holds a "plan" in its residual stream that constrains token generation multiple positions before execution.

**Metacognitive circuits**: The model has circuits that distinguish familiar vs. unfamiliar entities. These circuits determine whether to answer or profess ignorance. "Misfires" cause hallucinations — the "I know this" circuit fires on an unfamiliar entity, and the downstream "generate confident answer" pathway activates without genuine memory support.

**Refusal circuits**: Harmful request features are aggregated during finetuning from specific pretraining features. The RLHF process doesn't create new circuits — it amplifies and routes existing ones. This means jailbreaks that circumvent the "harmful request" aggregator can reach the underlying capable circuits.

These findings constrain future architecture design: any model aspiring to be mechanistically interpretable must maintain the **sparse, interpretable feature structure** that CLT-based analysis can recover. Dense, overlapping representations (superposition) will remain hard to interpret.

### 2.5 Kimi K2.5: Linear Attention + Hybrid Architecture

Kimi Linear (the base for the AttnRes paper's experiments) uses a hybrid attention strategy:

```
Layer composition: 3:1 ratio of KDA:MLA layers
  KDA (Kimi Delta Attention): linear-complexity attention using delta rule
    State update: S_t = S_{t-1} + β_t(v_t - S_{t-1}k_t^T)k_t
    Complexity: O(T·d²) not O(T²·d) — removes the T² bottleneck
    
  MLA: standard softmax attention with compressed KV cache
    Provides the "ground truth" attention for critical layers
    Uses NoPE (no positional encoding) in MLA layers
```

The NoPE layers in MLA are significant: without RoPE, attention weights are computed purely from content similarity, not position. This means context extension requires no modification (no YaRN or temperature rescaling). The trade-off is that long-range positional relationships must be handled by KDA layers.

**Kimi K2.5 full configuration** (from the benchmark table):
- 1T total parameters, 32B activated per token
- MoE: 256 routed experts + 1 shared expert (from Kimi Linear architecture scaled up)
- AttnRes: 6 layers per block, 9 blocks + embedding = 10 depth-wise sources
- GPQA: 87.6%, SWE-bench: 76.8%, AIME: 96.1%

### 2.6 JEPA and Energy-Based Models: The Missing Perspective

Joint Embedding Predictive Architectures (JEPA, LeCun et al.) take a fundamentally different approach to representation:

```
Standard LM objective:  minimize -log P(x_{t+1} | x_{1:t})  [token prediction]
JEPA objective:         minimize ‖s(x) - P(s(y))‖²          [latent prediction]

where:
  s(x) = encoder representation of context x
  s(y) = encoder representation of target y  (e.g., masked region)
  P(·) = predictor network operating in latent space
```

The key difference: JEPA avoids predicting in pixel/token space, instead predicting **abstract representations** of targets. This makes the model invariant to irrelevant low-level details (specific word choice, pixel texture) while being sensitive to high-level structure (meaning, object identity).

JEPA is not yet competitive with LLMs on language benchmarks. However, the theoretical connection is important: the functional anatomy of transformers revealed by interpretability research — abstract, language-independent features in middle layers — looks exactly like what JEPA learns by design. The convergence of empirical evidence (transformers learn abstract representations) with theoretical motivation (energy-based models should learn abstract representations) suggests that future architectures may explicitly design for this property.

---

## 3. Deep Dives: P/D Split, AFD, Attention, FFN, and Hardware Co-Design

### 3.1 The Bandwidth Wall: The Number That Governs Everything

Before diving into specific techniques, establish the fundamental constraint:

**Arithmetic Intensity (AI)** = FLOPS / bytes_read_from_memory

```
Matrix multiplication (batch size B, d_in, d_out):
  FLOPS = 2 × B × d_in × d_out
  Bytes = 2 × d_in × d_out × dtype_bytes  (read weights once) + B × (d_in + d_out) × dtype_bytes
  AI ≈ B  (proportional to batch size, dominant term for large matrices)

Hardware rooflines:
  H100 SXM: 3.35 TB/s bandwidth, 989 TFLOPS BF16
  Compute-bound threshold AI: 989e12 / 3.35e12 = 295 tokens/batch
  → Need batch ≥ 295 to be compute-bound; below that, bandwidth-limited
  
  Rubin GPU: 22 TB/s bandwidth, 35,000 TFLOPS FP4
  Compute-bound threshold: 35000e12 / 22e12 ≈ 1,590 tokens/batch
  → Even harder to saturate compute; bandwidth matters more
```

This analysis reveals that **single-user inference is always bandwidth-bound** regardless of GPU tier. The compute advantage of Rubin over H100 (35×) doesn't help single-user latency — the bandwidth advantage (6.6×) does. This is why the entire disaggregation stack is fundamentally a memory architecture problem, not a compute problem.

### 3.2 Prefill-Decode Disaggregation: The Mathematics

**Prefill** processes the full prompt in parallel. For prompt length T_p:

```
FLOPs (attention, one layer): 4 × T_p² × d_h × H + 4 × T_p × H × d_h²  ≈ 4T_p²d (for large T_p)
Memory access (weights):      4 × d² (Q,K,V,O projections) + 2 × d × d_ff (FFN)
Arithmetic intensity:         T_p × d / (4d²) ≈ T_p/d  (grows with prompt length)

At T_p = 4096, d = 7168:  AI = 4096/7168 ≈ 0.57  (still bandwidth bound, but less so)
At T_p = 128k, d = 7168:  AI = 128000/7168 ≈ 17.9  (still below H100 threshold of 295)
→ Prefill is always bandwidth-bound too, but benefits more from parallelism (T_p² attention FLOPS dominate)
```

**Decode** generates one token at a time (or K via speculative decoding):

```
FLOPs (attention, one step): 4 × T_current × d_h × H  (one query against all cached K,V)
                             + 4 × d × d_ff             (FFN)
Memory access (weights):     2 × d² × num_layers       (all weights, every step)
Memory access (KV cache):    2 × T_current × d_k × H_kv × num_layers  (all previous K,V)
Arithmetic intensity:        ~1 (batch=1 inference is compute-starved)
```

**The P/D split benefit — quantified**:

Without disaggregation (monolithic serving):
```
Decode throughput limit = min(
  HBM_bandwidth / weight_bytes_per_step,   # weight loading bottleneck
  HBM_bandwidth / kv_bytes_per_step        # KV cache bottleneck
)
```

With P/D disaggregation:
```
Dedicated decode nodes:  KV cache occupies full HBM; no weight-sharing with prefill
Dedicated prefill nodes: full compute utilization; no decode tail latency
  
Result: 2-3× decode throughput, <50% TTFT vs monolithic at equivalent hardware cost
```

**NVIDIA Dynamo** implements this as a scheduling framework:
```python
# Pseudocode for P/D aware scheduling
class DynamoScheduler:
  prefill_pool: List[GPU]   # compute-optimized, large batch sizes
  decode_pool: List[GPU]    # bandwidth-optimized, KV-dedicated HBM
  kv_router: KVAwareLoadBalancer  # routes by KV cache affinity
  
  def schedule(request):
    # Step 1: Route to prefill node with most relevant prefix cache
    prefill_node = kv_router.find_best_prefill(request.prompt_prefix)
    
    # Step 2: Prefill, generate KV cache
    kv_cache = prefill_node.prefill(request)
    
    # Step 3: Transfer KV over RDMA to decode node
    decode_node = kv_router.find_decode_node(load_balance=True)
    decode_node.transfer_kv(kv_cache)  # RDMA, ~10 GB/s NVLink bandwidth
    
    # Step 4: Decode until stop condition
    return decode_node.decode(request, kv_cache)
```

**KV transfer cost**: For a 685B MoE model (60 MLA layers, d_c=512, FP8):
```
KV size per token: 60 layers × d_c × 1B = 60 × 512 × 1 = 30.7 KB/token
At 8k prompt: 30.7KB × 8192 = 252 MB
Transfer time (NVLink 6, 2TB/s): 252MB / 2000GB/s ≈ 0.13 ms  (negligible)
Transfer time (InfiniBand HDR, 200GB/s): 252MB / 200GB/s ≈ 1.26 ms  (non-trivial)
→ MLA's KV compression directly enables fast P/D transfer; standard MHA would be ~130× larger
```

### 3.3 Attention-FFN Disaggregation: The Next Level

AFD disaggregates **within the decode phase**, exploiting the differential hardware requirements of attention vs FFN during token generation.

**Why attention and FFN have different hardware optima**:

```
Attention during decode (one token, full KV cache):
  Operation: Q_new · K_cache^T (shape: [1, T_ctx])
  KV cache read: 2 × T_ctx × d_k × H_kv bytes (dynamic, grows with context)
  Weight read:   d × (d_k + d_v + d) bytes (fixed per token)
  Nature: STATEFUL — access pattern depends on full KV history
  Hardware needs: large HBM for KV cache, random access patterns
  
FFN/MoE during decode (one token):
  Operation: token × W_gate, W_up, W_down (or sparse expert subset)
  Weight read:   K × (d × d_ff_expert × 3) bytes (fixed per token, expert-dependent)
  Nature: STATELESS — same weights regardless of history, deterministic access
  Hardware needs: fast sequential SRAM reads, no dynamic state
```

**LPU advantage for FFN**:

Groq LPU architecture:
```
SRAM: 500MB on-chip (LPU gen 3 / LP30)
SRAM bandwidth: ~5,000 GB/s (estimated from ISCA 2020 paper)
DRAM access: 256 GB DDR5 via FPGA (for KV cache / draft models)
Compute: 1.2 PFLOPS FP8

For FFN computation (gpt-oss-120b, 5.1B active, FP8 = 5.1 GB):
  If model fits in SRAM: latency = 5.1GB / 5000 GB/s = 1.02 ms → ~980 tok/s
  If DRAM: 5.1GB / 200 GB/s = 25.5 ms → ~39 tok/s
  
Groq's 500 tok/s figure for gpt-oss-120b suggests partial SRAM fit (~5B active parameters just fits)
```

**AFD ping-pong pipeline** (from MegaScale-Infer paper [ByteDance2025]):

```
Each transformer layer: Attention → Router → FFN

AFD assigns:
  GPU cluster: handle attention (KV-heavy, stateful)
  LPU cluster: handle FFN computation (weight-heavy, stateless)

Token flow per layer:
  1. GPU computes attention: h_attn = Attention(h, KV_cache)   O(T × d) memory
  2. GPU routes tokens to LPU: dispatch(h_attn) → LPU         all-to-all collective
  3. LPU computes FFN:         h_ffn = FFN(h_attn)            O(d_ff) memory
  4. LPU returns to GPU:       combine(h_ffn) → GPU           reverse all-to-all
  5. GPU applies residual:     h_new = h_attn + h_ffn

Communication bottleneck: dispatch + combine = 2 × all-to-all per layer
  For 60 layers: 120 all-to-all operations per token
  Mitigation: ping-pong pipeline parallelism — overlap all-to-all with next layer's attention
```

**Quantitative AFD benefit** (from MegaScale-Infer):

```
Standard decode (one GPU cluster, 685B MoE):
  Per-token time = max(attention_time, ffn_time)
  Both compete for same HBM bandwidth

AFD (separate clusters):
  GPU attention time ≈ KV_cache_bytes / HBM_bandwidth
    = 2 × T × 60 × 512 × 1B / 22TB/s (Rubin)
    = 2 × 8192 × 60 × 512 / 22e12 = 45 μs per token at 8k context
  
  LPU FFN time ≈ active_weight_bytes / SRAM_bandwidth
    = 32B × 1B / 5000 GB/s = 6.4 ms  (for Kimi K2.5 32B active)
    → FFN is the bottleneck; LPU must process multiple tokens to amortize
  
  With batching on LPU (batch=16 tokens):
    LPU FFN time / token = 6.4ms / 16 = 0.4 ms
    GPU attention time unchanged = 45 μs
    System throughput: ~2500 tok/s (pipeline parallel GPU+LPU)
    vs. monolithic GPU: ~500 tok/s (HBM-bound)
```

### 3.4 Flash Attention: Fusing the Memory Bottleneck

Standard attention computes the full T×T attention matrix before multiplying by V. For T=4096, d_h=128:
```
Standard attention memory:
  S = Q × K^T:   T² × dtype = 4096² × 2B = 33.6 MB  (written to HBM)
  P = softmax(S): 33.6 MB  (written)
  O = P × V:      result from HBM reads
  Total HBM I/O: ~100 MB for one head, one layer
  
Flash Attention (Dao et al., 2022):
  Tile computation: process Q/K/V in blocks that fit in SRAM (e.g., 64×64 tiles)
  Online softmax: maintain running max m and log-sum-exp ℓ per tile
    m_new = max(m_old, row_max(S_tile))
    ℓ_new = e^{m_old - m_new} × ℓ_old + row_sum(e^{S_tile - m_new})
    O_new = e^{m_old - m_new}/ℓ_new × O_old + softmax(S_tile) × V_tile
  
  HBM I/O: O(T × d_h) — linear, not quadratic
  SRAM usage: O(block_size × d_h) — fits in L2 cache
  
Flash Attention 3 (2024): adds asynchronous WGMMA+TMA pipeline on H100
  Achieves ~750 TFLOPS on H100 (75% of theoretical peak) vs ~350 for FA2
```

### 3.5 Paged Attention and KV Cache Management

Traditional KV cache pre-allocates max_seq_len × num_layers × kv_dim for each request. For max_seq_len=32k, this wastes memory when actual sequence is short.

**vLLM's PagedAttention** (Kwon et al., 2023):

```
KV cache managed as fixed-size blocks (pages), like OS virtual memory:
  Block size: 16-32 tokens (configurable)
  Block table: maps (request_id, block_index) → physical_block_id
  
Benefits:
  1. No fragmentation: sequences of different lengths share same block pool
  2. Copy-on-write: beam search / speculative decoding share prefix blocks
  3. Prefix caching: identical system prompts share physical blocks across requests
  
Memory efficiency improvement:
  Naive: 60-80% GPU memory wasted due to over-allocation and fragmentation
  PagedAttention: ~4% waste (only within-block fragmentation)
  → 2-4× more concurrent requests per GPU
```

**Prefix caching** (also called prompt caching):

For enterprise deployments where many requests share a long system prompt (e.g., 8k token RAG context):
```
Without prefix caching:
  Cost = T_system × T_user × num_requests × compute_per_token
  At 8k system prompt, 1k user query, 10k requests: 90B token-compute

With prefix caching (hit rate ~80%):
  First request: full prefill (8k + 1k = 9k tokens)
  Subsequent hits: only user query prefilled (1k tokens)
  Savings: 8k × 8000 requests × compute_per_token = 89% reduction in prefill compute
  
Anthropic prompt caching pricing:
  Cache write: $3.75/MTok (Claude Sonnet 4.6)
  Cache read:  $0.30/MTok (vs $3.00/MTok for fresh input)
  → 90% cost reduction on cached tokens
```

### 3.6 AttnRes Two-Phase Inference: The Memory Access Analysis

The AttnRes paper's key system contribution is showing that Block AttnRes adds only 2% inference latency overhead. Here is the derivation:

```
Setup: L=128 layers, N=8 blocks, S=L/N=16 layers/block, d=7168

Standard residual per-layer memory access:
  Read: h_{l-1} (1 × d) + model weights
  Write: h_l (1 × d)
  Residual I/O: 2d reads, d writes = 3d total
  
Block AttnRes (two-phase):
  Phase 1 (amortized over S=16 layers in a block):
    Read N=8 block KV pairs: 2×N×d = 2×8×7168 = 114,688 bytes
    Amortized per layer: 2×N/S × d = (N/S) × d  (since divided by S=16)
    = (8/16) × d = 0.5d per layer
    Write: 1 output per layer: d
    Phase 1 I/O per layer: (N/S + 1)d = (0.5+1)d = 1.5d
  
  Phase 2 (sequential, within-block):
    Read: partial_block (1×d) + block output (1×d)
    Write: updated h_l (1×d)
    Phase 2 I/O per layer: 3d  (same as standard)
  
  Total Block AttnRes I/O per layer: Phase 1 + Phase 2 = 1.5d + 3d = 4.5d
  vs Standard: 3d
  Overhead: 4.5/3 = 1.5× memory access for the residual mechanism

But: residual mechanism I/O is much smaller than weight loading I/O:
  Weight I/O per layer ≈ 4d² (attention) + 3d×d_ff (FFN)
    ≈ 4×7168² + 3×7168×18944 = 206M + 407M bytes ≈ 613M per layer
  Residual overhead: (4.5-3)×7168 = 10.7 KB additional
  Overhead fraction: 10.7KB / 613MB = 0.0017%  (vanishingly small)

The paper's <2% inference latency claim is well-grounded.
```

**Table 1 from the paper reproduced and annotated**:

| Mechanism | Total I/O per token per layer | Notes |
|-----------|------------------------------|-------|
| Standard Residuals | 3d | Read h_{l-1} and write h_l |
| mHC (m=4 streams) | (8m+2)d + 2m² + 4m ≈ 34d | 4 streams; expensive |
| AttnRes Full | (S+N)d = 24d (typical) | N=8, S=2 amortization |
| AttnRes Block | (N/S + 5)d ≈ 5.5d | N=8, S=16: most efficient |

Block AttnRes achieves 5.5d vs 34d for mHC — 6× lower I/O for comparable performance.

### 3.7 MoE Expert Parallelism: The Systems Challenge

Deploying a 685B MoE model across a cluster requires careful parallelism strategy:

```
Total parameter budget: 685B = shared_params + expert_params
  Shared: embedding + attention + shared experts ≈ ~85B
  Expert: 256 experts × (d × d_ff × 3) ≈ 600B

Tensor Parallel (TP) degree T_p for attention/shared params:
  Each GPU holds d/T_p of each parameter
  Requires all-reduce after each attention computation: O(T × d) communication

Expert Parallel (EP) degree E_p for MoE:
  Each GPU holds N_e/E_p experts (e.g., E_p=64 → 4 experts/GPU)
  Each forward pass requires all-to-all routing: O(T × d_expert) communication
  
Combined (DeepSeek V3 deployment on H100 cluster):
  TP=8 for attention layers (NVLink within a node)
  EP=32 for MoE layers (across nodes via InfiniBand)
  Total: 8 × 32 = 256 GPUs for full 685B model
  
All-to-all communication cost (EP=32, token-level):
  Each token dispatched to 8/256 experts = 3.1% chance on any GPU
  All-to-all volume: T × K × d_expert (K=8 active experts)
  At T=2048, K=8, d_expert=2048, FP8: 2048 × 8 × 2048 × 1B = 33.6 MB
  At InfiniBand HDR 200GB/s bidirectional: 33.6MB / 200GB/s = 0.17 ms
  → Expert routing adds ~0.17ms per MoE layer; 60 layers → ~10ms per forward pass
```

This communication overhead explains why MoE models have higher latency than dense models of equivalent active parameter count — and why AFD's LPU integration must maintain tight GPU-LPU interconnect (<1ms round-trip for the dispatch/combine cycle).

### 3.8 Speculative Decoding: Multiplying Throughput Without Quality Loss

Standard decode generates one token per forward pass. Speculative decoding (Leviathan et al., 2023) generates K tokens per pass using a small draft model:

```
Algorithm: Speculative Decoding
Input: context x[1..T], target model M, draft model M_small, K speculation steps

1. Draft phase: M_small generates K candidate tokens x̂[T+1..T+K]
   Cost: K × cost(M_small)  (cheap)

2. Verification phase: M processes x[1..T] + x̂[T+1..T+K] in parallel (one forward pass)
   Cost: 1 × cost(M) with T+K context
   
3. Accept/reject: compare M and M_small token distributions
   Accept x̂[t] if: uniform(0,1) < min(1, P_M(x̂[t]) / P_Msmall(x̂[t]))
   
4. Return all accepted tokens (expectation ≥ 1, often 1.5-2.5)

Throughput improvement:
  Without spec decoding: 1 token / cost(M)
  With spec decoding:    E[accepted] / (cost(M) + K×cost(M_small))
  
  If E[accepted] = 2.0, K=4, cost(M_small) = 0.1×cost(M):
  Speedup = 2.0 / (1.0 + 0.4) = 1.43×
  
  DeepSeek V3 with MTP heads as draft:
    MTP head forward pass ≈ 0.02×cost(M) (tiny head on top of existing residual stream)
    E[accepted] ≈ 1.7-2.0 (domain-dependent)
    Speedup ≈ 1.7 / (1.0 + 4×0.02) = 1.56×
```

**Groq LPU + speculative decoding** (from GTC 2026 SemiAnalysis):
```
Draft on LPU (small model in SRAM): latency ≈ 0.5ms per draft token
Verify on GPU (large model):        latency ≈ 1.2ms per full forward pass
With K=4 draft tokens, E[accepted]=2.0:
  Total latency: 4×0.5ms + 1.2ms = 3.2ms for ~2.0 tokens
  Effective per-token: 1.6ms → 625 tok/s  (vs 833 tok/s theoretical GPU bandwidth limit)
→ Spec decoding with LPU draft is competitive with, but not superior to, raw AFD for this model size
```

---

## 4. Forward-Looking R&D: Grounded Technical Speculation

### 4.1 The Interpretability-Architecture Feedback Loop

The most consequential long-term research direction is the feedback loop between mechanistic interpretability findings and architecture design. This is genuinely novel: for the first time, we are gaining the ability to observe what computations a trained model performs, and can use that observation to design better training objectives.

**Current state**: Anthropic's circuit tracing reveals that Claude 3.5 Haiku uses genuine multi-step reasoning, forward planning, and metacognitive circuits — but these emerged from next-token prediction training, not from explicit architectural pressure.

**Near-term**: AttnRes is an early example of using depth-wise structural knowledge (the PreNorm dilution problem, the value of selective layer retrieval) to improve architecture. The GPQA gain (+7.5 points) specifically on multi-step reasoning tasks confirms the mechanism: deeper layers can now retrieve representations from earlier processing stages, supporting multi-hop inference chains.

**Medium-term**: If we can identify which circuit patterns correspond to which capabilities (e.g., "metacognitive circuits correlate with calibrated uncertainty"), we can design training objectives that explicitly reward their formation:

```python
# Hypothetical interpretability-driven training objective
def augmented_loss(model, batch):
    standard_loss = cross_entropy(model(batch), batch.labels)
    
    # Detect metacognitive circuit activation on uncertain examples
    uncertain_mask = (batch.labels.entropy > threshold)
    circuits = extract_circuits(model, batch[uncertain_mask])
    metacog_active = circuits['metacognitive_confidence'].mean()
    
    # Reward metacognitive circuit activation on uncertain examples
    circuit_bonus = lambda * metacog_active * uncertain_mask.float().mean()
    
    return standard_loss - circuit_bonus
```

This is speculative, but the components exist: CLT-based circuit extraction, activation steering, intervention experiments. The missing piece is reliable automated circuit identification at scale (current tools are human-in-the-loop).

**Long-term — trained-for-interpretability models**: If AttnRes's learned attention weights over depth become standard, and if we can observe these weights during training, we have a direct window into how information is being routed through the model. This is a trainable version of the attribution graph — not an approximation via a replacement model, but the model's own routing decisions, expressed as explicit attention weights.

### 4.2 AttnRes + Full AttnRes: The Future Hardware Unlock

The Block AttnRes paper explicitly states:

> "We anticipate that future interconnect improvements will make the full O(Ld) communication practical, fully realizing the potential of Full AttnRes."

The roadmap from Block to Full AttnRes requires:
- Current: N=8 blocks → 8 stored hidden states per token
- Target: N=L → L individual layer outputs retained

For L=128 layers, d=7168, FP8: 128 × 7168 × 1 byte = 917 KB per token.
At batch size 256: 256 × 917 KB = 235 MB of additional SRAM or ultra-fast cache per device.

NVIDIA's Rubin Ultra platform (NVL576, announced GTC 2026) with LP40 (LPU gen 4 with hybrid-bonded DRAM from SK Hynix) introduces a small quantity of near-SRAM-latency DRAM stacked directly on the chip. This is the enabling technology for Full AttnRes in the 2027-2028 timeframe:

```
LP40 memory hierarchy (projected):
  SRAM (on-die):          500 MB at ~5,000 GB/s
  Hybrid-bonded DRAM:     ~4 GB at ~1,000 GB/s  (10-15ns latency vs 80ns for HBM)
  HBM4:                   288 GB at 22 TB/s

Full AttnRes overhead with hybrid-bonded DRAM:
  Per-token layer output storage: 917 KB (fits in 4 GB hybrid DRAM)
  Access bandwidth needed: 917 KB × 128 layers × generation_rate
  At 1000 tok/s: 917 KB × 128 × 1000 = 117 GB/s  (well within 1TB/s hybrid-bonded)
  → Full AttnRes becomes practical with LP40
```

**Architectural implication**: Once Full AttnRes is hardware-feasible, the optimal transformer architecture shifts further toward depth (more layers, narrower width), and models can be designed with an explicit "working memory" register — each layer maintains learned weights over its entire computational history.

### 4.3 KV Cache as a Distributed Service: The CXL Future

The compute/memory disaggregation trend ultimately terminates in a clean separation:
- GPUs: pure compute (attention + FFN)
- Separate memory fabric: KV cache storage

The enabling technology is **CXL (Compute Express Link) 3.0**, which allows memory pooling across nodes with cache-coherent access at ~100ns latency (vs 1μs for NVMe, ~1ns for HBM).

```
Current architecture:
  GPU HBM: model weights + KV cache (shared, competing)
  KV cache limit: HBM_capacity - weight_bytes
  Example (H100 80GB, 7B model in FP8 = 7GB): 73GB for KV cache
    = 73GB / (2 × layers × d_kv × dtype) = ~128k tokens at 8k context

CXL-disaggregated architecture:
  GPU HBM: model weights only (full HBM available for compute)
  CXL memory pool: KV cache (terabytes, many GPUs sharing)
  
KV cache pooling benefit:
  Current: each GPU maintains its own KV cache → requests cannot migrate between GPUs
  CXL-shared: any GPU can serve any request (KV cache in shared pool)
  → 2-3× more efficient GPU utilization through KV-aware load balancing
  → Supports ultra-long context (millions of tokens) without per-GPU memory limits

Latency impact (CXL KV fetch at 100ns vs HBM at 0.5ns):
  For 128k token context, attention reads T_ctx × d_kv per token:
    Local HBM: 128k × 512B = 65MB → 65MB/22TB/s = 3 μs
    CXL: 128k × 512B = 65MB → 65MB/1TB/s = 65 μs  (20× slower)
  
  Mitigation: KV prefetching (stream next likely tokens' KV into HBM during current attention)
  With 99% prefetch hit rate: CXL overhead ≈ 1% → acceptable
```

**Historical parallel**: The separation of compute (CPU) and memory (DRAM) in classical computing took decades to fully optimize (prefetching, caching hierarchies, NUMA architectures). LLM infrastructure is recapitulating this evolution at 100× speed due to commercial pressure.

### 4.4 The Sequence-Depth Duality: Implications for Architecture Search

The AttnRes paper formalizes a profound theoretical connection: **residual connections over depth are isomorphic to recurrence over sequences**. Both are instances of the same family of structured state updates:

```
Sequence (time) domain:
  RNN recurrence:    s_t = A·s_{t-1} + B·x_t         (linear)
  Attention:         s_t = softmax(Q_t·K_{1:t}^T)·V_{1:t}  (softmax)

Depth domain:
  Standard residual: h_l = h_{l-1} + f_{l-1}(h_{l-1})      (linear, M=1)
  Highway:           h_l = (1-g)·h_{l-1} + g·f_{l-1}(h)    (gated linear, M=1-semiseparable)
  mHC:               H_l = H_{l-1}A + f(H_{l-1}α)β^T       (multi-state linear, M=m-semiseparable)
  AttnRes:           h_l = Σ α_{i→l}·v_i                    (softmax, M=dense)
```

This duality predicts that **every sequence-modeling innovation has a depth-modeling analogue**:

| Sequence innovation | Depth analogue | Status |
|---------------------|----------------|--------|
| RNN → Transformer (linear → softmax attention) | Standard residual → AttnRes | Done [Kimi2026] |
| Multi-head attention | Multi-head depth attention | Tested; hurts (depth mixture uniform across channels) |
| Flash Attention (IO-efficient) | Two-phase block attention | Done [Kimi2026] |
| Sliding window attention | Sliding window depth (SWA) | Tested; worse than global AttnRes |
| Rotary positional embedding | Depth positional embedding? | Not yet explored |
| KV cache (cached sequence context) | Cached block representations | Done [Kimi2026] |
| Speculative decoding | Speculative layer execution? | Research direction |
| Linear attention (SSM) | Linear depth attention | Prior art (mHC, DDL) |

The **speculative layer execution** direction deserves elaboration:

```python
# Hypothetical: speculative depth (SLD)
# Observation: if AttnRes weights are stable across similar inputs,
# we can predict h_l from h_{l-2} without computing h_{l-1}

def speculative_layer_decode(x, model, skip_layers=[10, 20, 30]):
    h = model.embed(x)
    for l in range(L):
        if l in skip_layers:
            # Draft: use AttnRes weights to predict h_l directly from block reps
            h_draft = model.layers[l].attnres_predict(block_reps)  # fast
            # Run full layer
            h_full = model.layers[l](h)
            # Verify: if draft is close, accept; else recompute
            if cosine_sim(h_draft, h_full) > threshold:
                h = h_draft  # skip full layer
            else:
                h = h_full
    return h
```

This is speculative but grounded: AttnRes learns nearly input-independent routing weights (the pseudo-query w_l is input-independent by design). The learned weights are approximately fixed for a given layer-position, enabling prediction of the output representation without running the full forward pass.

### 4.5 JEPA Integration: Latent Prediction as an LLM Training Objective

Energy-based models (JEPA, Hinton's Hopfield networks) offer a different inductive bias than next-token prediction. The convergence of interpretability findings with JEPA theory is striking:

```
JEPA learns:  representations x,y share abstract structure, abstracted from surface form
LLM learns:   (empirically) abstract, language-independent features in middle layers

JEPA + LLM hybrid training objective:
  L = L_token_pred + λ · L_JEPA

  L_JEPA = E[‖s_encoder(x_context) - P(s_encoder(x_target))‖²]
  
  where x_target = x with some tokens masked
  and   s_encoder = middle-layer representations (the reasoning cortex)
```

This would explicitly train the model to develop abstract, context-invariant representations — potentially making the latent features more aligned with the interpretable features Anthropic's CLT finds. The training overhead is modest (one extra encoder forward pass per batch), and the representation regularization could dramatically improve probe accuracy.

**Who is incentivized to pursue this**: Meta's FAIR group (LeCun's JEPA is their primary bet), Google DeepMind (JEPA aligns with their neuroscience-inspired research agenda), Anthropic (interpretability-driven training is a core safety priority). OpenAI is least likely — their empirical scaling approach doesn't require principled representation theory.

### 4.6 Geopolitical and Resource Constraints: Shaping the Architecture Landscape

Architecture choices are not made in a vacuum. The geopolitical context shapes which directions receive investment:

**The US export control regime** (Bureau of Industry and Security export controls on advanced AI chips to China) has created a bifurcated chip landscape:
```
Unrestricted: H100/H200/B200/Rubin → US, EU, Japan, Korea, Taiwan, India
Restricted: A800/H800 (export-control-compliant) → China (limited)
Further restricted: post-Oct 2023 controls → China receives even less capable chips

Impact on Chinese lab architecture choices:
  1. Constrained bandwidth → more emphasis on MoE (reduce active compute per token)
  2. Smaller clusters → more efficient P/D disaggregation within single data center
  3. Software optimization priority → custom CUDA/Triton kernels, NKI equivalents
  4. DeepSeek's efficiency innovations (MLA, MTP, aux-free load balancing) emerge partly
     from hardware constraints, not choice
```

**The Samsung SF4 factor**: The Groq LPU gen 3 (LP30) uses Samsung SF4X (4nm class at Samsung's Austin fab, US domestic). This allowed NVIDIA to access LPU production without competing for TSMC N3 allocation (already constrained for Blackwell/Rubin). This is a direct example of architecture choice (SRAM-centric LPU) enabling geopolitical agility (US-domestic supply chain).

**Open-weight model dynamics**: The Alibaba (Qwen), MoonshotAI (Kimi), and ZhipuAI (GLM) model families demonstrate that Chinese labs can train frontier-quality models on export-control-compliant hardware, given sufficient software engineering investment. AttnRes is a clear example: a training efficiency improvement (1.25× compute equivalent) that costs zero additional compute at inference — exactly the kind of algorithmic arbitrage that partially compensates for hardware disadvantage.

**Historical parallel**: The US-USSR competition in aerospace drove rapid innovation on both sides. The party with hardware constraints (USSR in precision manufacturing, China in advanced chips) develops algorithmic compensation strategies that ultimately generalize. AttnRes may be China's "solid rocket booster equivalent" — a constraint-born innovation that proves superior and gets adopted universally.

### 4.7 The Next Disaggregation Level: Zone Separation

Based on the functional anatomy (input zone / reasoning cortex / output zone), the next logical disaggregation is:

```
Level 3 disaggregation: zone-aware routing

Input zone (layers 1-10%, L=1-13 for a 128-layer model):
  - Format decoding, entity recognition
  - Operations: sequence attention + FFN over short context
  - Hardware target: inference chip at cloud edge (low-cost, low-latency access)
  - Typical sequence: user query → tokenize → embed → early layers

Reasoning cortex (layers 10-90%, L=13-115):
  - Abstract computation, multi-hop reasoning
  - Operations: full attention + MoE over long context
  - Hardware target: high-compute cluster (H200/Rubin + LPU AFD)
  - This is where the "thinking" happens

Output zone (layers 90-100%, L=115-128):
  - De-embedding, format encoding, refusal circuits
  - Operations: token-space mapping, safety circuit application
  - Hardware target: inference chip (symmetric with input zone)

Potential benefit:
  Input/output zones: 20% of compute, can run on 5× cheaper hardware
  Reasoning cortex: 80% of compute, stays on expensive GPUs
  Cost reduction: 20% × 0.2 + 80% × 1.0 = 0.84× → 16% cost reduction
  Latency benefit: input zone on edge → TTFT reduced by zone latency
  
Prerequisite: AttnRes with zone-aware block boundaries
  Zone boundaries = block boundaries in Block AttnRes
  Natural extension: different hardware handles different blocks
```

This is speculative but follows inevitably from the trend: each generation of disaggregation finds a new axis along which LLM inference can be decomposed. The AttnRes paper inadvertently provides the infrastructure for zone disaggregation by creating explicit block boundaries.

### 4.8 Test-Time Compute Allocation: Beyond Flat Chain-of-Thought

Current reasoning models (Claude Sonnet 4.6 in adaptive mode, GPT-o3) allocate test-time compute through chain-of-thought tokens: the model "thinks out loud," and the thinking tokens consume additional KV cache and attention compute.

The inefficiency: thinking tokens are processed identically to output tokens, with the same per-token compute cost. But not all thinking is equal — some CoT steps are simple format transitions, others are genuine multi-hop reasoning.

**Grounded direction: adaptive depth routing**

AttnRes's block structure enables a compelling extension:

```python
# Pseudocode: adaptive depth inference
# "Easy" tokens skip the reasoning cortex; "hard" tokens get more passes

def adaptive_depth_forward(x, model, difficulty_threshold=0.8):
    h, block_reps = model.input_zone(x)  # always full
    
    # Assess difficulty from input zone output
    difficulty = model.difficulty_head(h)  # lightweight probe
    
    if difficulty < difficulty_threshold:
        # Easy token: skip reasoning cortex, go directly to output zone
        return model.output_zone(h, block_reps[:2])  # only first 2 blocks
    else:
        # Hard token: full reasoning cortex (or multiple passes)
        n_passes = 1 + int(difficulty * 3)  # 1-4 passes based on difficulty
        for _ in range(n_passes):
            h, block_reps = model.reasoning_cortex(h, block_reps)
        return model.output_zone(h, block_reps)
```

This requires **difficulty estimation** — a small probe on the input zone output that predicts reasoning depth needed. This is an extension of the metacognitive circuits Anthropic found in Claude 3.5 Haiku: the model already develops circuits that assess its own knowledge limits; these could be externalized and used as routing signals.

The RYS experiment validates the principle: duplicating middle (reasoning cortex) layers improves benchmark performance. Adaptive depth routing is the inference-time analogue: allocate more "cortex passes" to harder problems.

### 4.9 Architecture Summary: The Likely 2027-2028 Frontier Model

Synthesizing all the above directions, the likely frontier architecture in 2027-2028:

```
Architecture: Sparse MoE + Hybrid Attention + Block AttnRes + Linear/NoPE layers

Layer composition (illustrative for 1T-scale model):
  - 200 transformer blocks
  - Hybrid attention: 3:1 KDA:softmax MLA ratio (from Kimi Linear)
  - Block AttnRes: 10-block partitioning (from Kimi2026, with future Full AttnRes transition)
  - Expert design: 512 routed + 2 shared, top-12 active per token
  - Active params: ~60B / 2T total

Inference serving architecture (2027):
  Prefill: GPU cluster (Rubin Ultra NVL144)
  Decode attention: GPU cluster (Rubin, KV-dedicated HBM)
  Decode FFN:       LPU cluster (LP40, hybrid-bonded DRAM, SRAM-fast weights)
  KV cache:         CXL memory pool (terabyte scale, <100ns latency)
  
  P/D disaggregation: L1
  AFD (attention-FFN): L2
  Zone disaggregation: L3 (experimental)
  KV-as-a-service: L4 (production)

Training improvements (2027):
  AttnRes (standard residual replacement): +1.25× effective compute
  MTP (K=4 prediction heads): +1.3× token efficiency
  Interpretability-guided training signals: TBD (active research)
  Muon optimizer: better gradient conditioning than Adam at scale
  
Benchmark projections (extrapolating current trends):
  GPQA-Diamond: >98% (human expert level)
  SWE-bench Verified: >90% (near-complete software engineering automation)
  AIME 2025: ~100% (already saturated)
  ARC-AGI-2: >85% (from current frontier ~75%)
```

---

## 5. Notes and References

### Technical Notes

**[N1] On the PreNorm dilution problem**: The O(L) growth of hidden state magnitude under PreNorm is not merely a training instability issue — it creates a fundamental capacity problem where the model cannot efficiently utilize depth. Tianyu Li et al. (SiameseNorm, 2026) provides the cleanest theoretical treatment, showing that the ratio of any single layer's contribution to the total hidden state diminishes as 1/l. The AttnRes solution (softmax over depth) is elegant precisely because it uses the same mathematical tool (attention) that solved the analogous problem for sequences.

**[N2] On the RYS experiment's statistical significance**: David Noel Ng's finding that duplicating middle layers (with zero gradient descent) tops the leaderboard is reproducible across multiple model families (Qwen2-72B, Mistral, LLaMA). The key constraint is that the performance peak is found at a specific layer window (middle 40-60% of depth), not uniformly across layers. This is the cleanest empirical validation of the three-zone anatomy. The effect size is also quantified: ~8.75% more compute (7/80 extra layers) producing top-1 leaderboard performance represents approximately the same benefit as training on ~2× more tokens (by Chinchilla scaling extrapolation).

**[N3] On Flash Attention's impact on sequence length scaling**: FA2/FA3 reduced the practical memory cost of attention from O(T²) to O(T), enabling the jump from 4k (GPT-4 original) to 1M+ token contexts. The hardware requirement remains: at 1M tokens, even O(T) attention means 1M × d_h bytes of Q/K activation memory. With d_h=128 and H=128 attention heads processed in parallel, this is 128 × 128k × 128 × 2B = 4.2 GB per attention layer per batch element — sustainable on Rubin (288 GB HBM) but requires careful memory management.

**[N4] On MLA's fundamental limit**: MLA's KV compression works by storing a d_c-dimensional latent per token and decompressing at attention time. The compression ratio d_c/(H×d_k) determines the quality-memory tradeoff. For DeepSeek V3 (d_c=512, H=128, d_k=128, so H×d_k=16384): compression ratio = 512/16384 = 3.1%. At this ratio, the latent representation must capture the projection of all future query vectors — a constraint that limits effectiveness for very long contexts where diverse queries are expected. This suggests MLA may have diminishing returns beyond certain context lengths.

**[N5] On the incentive alignment of NVIDIA's Groq acquisition**: The $20B figure ($20B to license IP and hire team, not a full acquisition) is extraordinary for a company with no profitable revenue at scale. The strategic logic: NVIDIA can deploy LPU-enhanced inference racks without competing for TSMC N3 allocation (LP30 uses Samsung SF4). This is a manufacturing supply chain play as much as a technology play. Historical analogue: Intel's acquisition of Altera (FPGAs) in 2015 for $16.7B to pursue heterogeneous compute — which ultimately failed due to integration difficulties. The NVIDIA-Groq integration succeeds where Intel-Altera failed because (a) LPU is narrowly specialized (not general-purpose like FPGA) and (b) AFD provides a clear system-level use case.

**[N6] On the AttnRes depth mixing matrix analysis (structured matrices)**: The paper's proof that all existing residual variants correspond to depth-wise linear attention, while AttnRes is depth-wise softmax attention, is a theoretical result with practical implications. The semiseparable rank M of the depth mixing matrix is: Standard residual: M=1, Highway: M=1, mHC: M=m (m parallel streams), AttnRes: M=L (dense). This is directly analogous to the expressivity hierarchy in sequence models: RNN (rank-1 state) < GRU (gated rank-1) < Transformer (full rank). AttnRes completes this hierarchy for depth.

**[N7] On the hardware feasibility of Full AttnRes**: The paper projects that future interconnects will enable Full AttnRes (N=L blocks). The calculation: for L=128 layers, storing all layer outputs requires 128 × d per token. At d=7168, FP8: 128 × 7168 × 1B = 917 KB per token. At batch=1024 tokens (long context): 917 KB × 1024 = 939 MB. NVIDIA's LP40 (Groq gen 4) with hybrid-bonded DRAM targets 4 GB of near-SRAM memory at ~1 TB/s bandwidth. Accessing 939 MB at 1 TB/s takes 0.9 ms — comparable to the computation time of a single layer. This makes Full AttnRes marginally feasible with LP40 but likely to require the LP50 generation (projected 2029) for comfortable deployment.

**[N8] On Kimi K2.5's KDA linear attention**: The delta rule update (S_t = S_{t-1} + β(v_t - S_{t-1}k_t^T)k_t) has a biological interpretation: it is the Widrow-Hoff learning rule applied online. The state S ∈ ℝ^{d×d} is a matrix that acts as an associative memory — it learns to predict v from k over the sequence. The update magnitude β controls the learning rate for each new key-value pair. This is mathematically identical to the "fast weight programmer" of Schmidhuber (1992), rediscovered independently by the modern linear attention literature. The hybrid KDA+MLA architecture uses linear attention (O(T)) for most layers (3/4) while preserving softmax attention (O(T²)) for the most critical layers (1/4) — a pragmatic engineering solution to the compute-expressivity tradeoff.

**[N9] On the relationship between JEPA and masked language modeling**: JEPA predicts in latent space; BERT-style masked LM predicts in token space. The key difference is that token-space prediction forces the model to capture low-level statistics (specific word choice, punctuation) to minimize cross-entropy loss. Latent-space prediction (JEPA) can choose a representation that discards prediction-irrelevant variability. This is why JEPA representations generalize better from fewer labels in downstream tasks. For LLM pretraining, a JEPA auxiliary objective would serve as a regularizer toward abstract representations — and the interpretability evidence suggests modern LLMs develop such representations anyway. JEPA would make this explicit and controllable.

**[N10] On the three-zone anatomy and pruning**: The finding from "The Unreasonable Ineffectiveness of the Deeper Layers" (Gromov et al., 2025) that a significant fraction of layers can be pruned with minimal loss is directly explained by the three-zone anatomy + PreNorm dilution: middle layers that fail to gain influence over the accumulated residual (due to dilution) gradually learn to output near-zero, effectively becoming no-ops. AttnRes's selective aggregation prevents this by always maintaining a pathway for each layer to influence downstream computation. Post-AttnRes, layer pruning should show different (lower) pruning resilience, because each layer genuinely contributes due to the learned routing.

---

### References

#### Primary Sources (Papers)

[1] Kimi Team. "Attention Residuals." Technical Report, MoonshotAI, March 2026. https://github.com/MoonshotAI/Attention-Residuals

[2] Lindsey, J., Gurnee, W., Ameisen, E., et al. "On the Biology of a Large Language Model." Transformer Circuits Thread, Anthropic, March 2025. https://transformer-circuits.pub/2025/attribution-graphs/biology.html

[3] Lindsey, J. et al. "Circuit Tracing: Revealing Computational Graphs in Language Models." Transformer Circuits Thread, Anthropic, March 2025. https://transformer-circuits.pub/2025/attribution-graphs/methods.html

[4] Ng, D.N. "LLM Neuroanatomy: How I Topped the LLM Leaderboard Without Changing a Single Weight." Personal blog, March 2026. https://dnhkng.github.io/posts/rys/

[5] DeepSeek-AI et al. "DeepSeek-V3 Technical Report." arXiv:2412.19437, 2025.

[6] Zhu, D. et al. "Hyper-Connections." arXiv:2409.19606, 2025.

[7] Xie, Z. et al. "mHC: Manifold-Constrained Hyper-Connections." arXiv:2512.24880, 2026.

[8] Zhang, Y. et al. "Kimi Linear: An Expressive, Efficient Attention Architecture." arXiv:2510.26692, 2025.

[9] Dao, T., Fu, D., Ermon, S., Rudra, A., Ré, C. "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness." NeurIPS 2022.

[10] Dao, T. "FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning." ICLR 2024.

[11] Shah, J. et al. "FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-Precision." arXiv:2407.08608, 2024.

[12] Kwon, W. et al. "Efficient Memory Management for Large Language Model Serving with PagedAttention." SOSP 2023.

[13] He, K., Zhang, X., Ren, S., Sun, J. "Deep Residual Learning for Image Recognition." CVPR 2016. arXiv:1512.03385

[14] Xiong, R. et al. "On Layer Normalization in the Transformer Architecture." ICML 2020. arXiv:2002.04745

[15] Zhang, B., Sennrich, R. "Root Mean Square Layer Normalization." NeurIPS 2019.

[16] Vaswani, A. et al. "Attention is All You Need." NeurIPS 2017.

[17] Su, J. et al. "RoFormer: Enhanced Transformer with Rotary Position Embedding." arXiv:2104.09864, 2021.

[18] Leviathan, Y., Kalman, M., Matias, Y. "Fast Inference from Transformers via Speculative Decoding." ICML 2023.

[19] Chen, C., Borgeaud, S., Irving, G. et al. "Accelerating Large Language Model Decoding with Speculative Sampling." arXiv:2302.01318, 2023.

[20] Srivastava, R.K., Greff, K., Schmidhuber, J. "Highway Networks." arXiv:1505.00387, 2015.

[21] Pagliardini, M. et al. "DenseFormer: Enhancing Information Flow in Transformers via Depth Weighted Averaging." arXiv:2402.02622, 2024.

[22] Li, T. et al. "SiameseNorm: Breaking the Barrier to Reconciling Pre/Post-Norm." arXiv:2602.08064, 2026.

[23] Geva, M., Schuster, R., Berant, J., Levy, O. "Transformer Feed-Forward Layers Are Key-Value Memories." EMNLP 2021.

[24] Gromov, A. et al. "The Unreasonable Ineffectiveness of the Deeper Layers." arXiv:2403.17887, 2025.

[25] Yang, B. et al. "Rope to Nope and Back Again: A New Hybrid Attention Strategy." arXiv:2501.18795, 2025.

[26] Chen, C., Wei, L. "Post-LayerNorm Is Back: Stable, ExpressivE, and Deep." arXiv:2601.19895, 2026.

[27] Milakov, M., Gimelshein, N. "Online Normalizer Calculation for Softmax." arXiv:1805.02867, 2018.

[28] Liu, J. et al. "Muon is Scalable for LLM Training." arXiv:2502.16982, 2025.

[29] Dao, T., Gu, A. "Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Space Duality." arXiv:2405.21060, 2024.

[30] Knupp, J. et al. "Depth-Recurrent Attention Mixtures: Giving Latent Reasoning the Attention it Deserves." arXiv:2601.21582, 2026.

[31] Zhang, Y. et al. "Deep Delta Learning." arXiv:2601.00417, 2026.

[32] Hoffmann, J. et al. "Training Compute-Optimal Large Language Models." (Chinchilla) arXiv:2203.15556, 2022.

[33] Pope, R. et al. "Efficiently Scaling Transformer Inference." arXiv:2211.05102, 2022.

[34] Yang, S. et al. "Gated Linear Attention Transformers with Hardware-Efficient Training." ICML 2024.

[35] Sun, Y. et al. "Learning to (Learn at Test Time): RNNs with Expressive Hidden States." arXiv:2407.04620, 2024.

[36] Xiao, G. et al. "Efficient Streaming Language Models with Attention Sinks." arXiv:2309.17453, 2023.

[37] ByteDance. "MegaScale-Infer." arXiv:2504.02263, 2025. (AFD original paper)

[38] Stepfun. "Step-3." arXiv:2507.19427, 2025. (AFD production deployment)

[39] Kaplan, J. et al. "Scaling Laws for Neural Language Models." arXiv:2001.08361, 2020.

[40] Touvron, H. et al. "LLaMA: Open and Efficient Foundation Language Models." arXiv:2302.13971, 2023.

#### Industry / Technical Reports

[41] Patel, D., Xie, M., Nishball, D. et al. "Nvidia – The Inference Kingdom Expands: GTC 2026 Recap." SemiAnalysis, March 24, 2026. https://newsletter.semianalysis.com/p/nvidia-the-inference-kingdom-expands

[42] Chu, W., Patel, D., Nishball, D. et al. "Vera Rubin – Extreme Co-Design: An Evolution from Grace Blackwell Oberon." SemiAnalysis, February 25, 2026. https://newsletter.semianalysis.com/p/vera-rubin-extreme-co-design-an-evolution

[43] Patel, D. "Groq Inference Tokenomics: Speed, But at What Cost?" SemiAnalysis, 2024. https://newsletter.semianalysis.com/p/groq-inference-tokenomics-speed-but

[44] Patel, D. "Project Rainier: AWS Trainium3 Deep Dive." SemiAnalysis, 2025.

[45] NVIDIA. "NVIDIA Dynamo: Disaggregated Serving Framework." GitHub, 2025. https://github.com/ai-dynamo/dynamo

[46] Groq. "Groq ISCA 2020 Paper: A Domain-Specific Architecture for Linear Algebra." IEEE Micro, 2020.

[47] Anthropic. "Claude Sonnet 4.6 System Card." March 2026.

[48] DeepSeek-AI. "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning." arXiv:2501.12948, 2025.

[49] Zheng, L. et al. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." NeurIPS 2023.

[50] Artificial Analysis. "LLM Performance Benchmarks." March 2026. https://artificialanalysis.ai

[51] OpenRouter. "State of AI 2025: 100 Trillion Tokens." 2025. https://openrouter.ai/state-of-ai

[52] TrendForce. "AI Server Chip Market Forecast 2026." February 2026.

[53] Menlo Ventures. "2025: The State of Generative AI in the Enterprise." 2025. https://menlovc.com/perspective/2025-the-state-of-generative-ai-in-the-enterprise/

#### Related Background

[54] LeCun, Y. "A Path Towards Autonomous Machine Intelligence." Position paper, Meta AI, 2022.

[55] Assran, M. et al. "Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture." CVPR 2023. (Image-JEPA)

[56] Hopfield, J. "Neural networks and physical systems with emergent collective computational abilities." PNAS 1982. (associative memory; precursor to attention)

[57] Schmidhuber, J. "Learning to control fast-weight memories: An alternative to dynamic recurrent networks." Neural Computation 4(1), 1992. (fast weight programmers)

[58] Katharopoulos, A. et al. "Transformers are RNNs: Fast Autoregressive Transformers with Linear Attention." ICML 2020.

[59] Tan, S. et al. "Scaling Stick-Breaking Attention." ICLR 2025.

[60] Zhou, Z. et al. "Value Residual Learning." ACL 2025.

[61] Menghani, G., Kumar, R., Kumar, S. "LAuReL: Learned Augmented Residual Layer." arXiv:2411.07501, 2025.

[62] Xiao, D. et al. "MUDDFormer: Breaking Residual Bottlenecks in Transformers via Multiway Dynamic Dense Connections." ICML 2025.

[63] Yang, Y., Gao, J. "mHC-lite: You Don't Need 20 Sinkhorn-Knopp Iterations." arXiv:2601.05732, 2026.

[64] Narayanan, D. et al. "Efficient Large-Scale Language Model Training on GPU Clusters Using Megatron-LM." arXiv:2104.04473, 2021.

[65] Shazeer, N. et al. "Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer." ICLR 2017.

---

*This document was compiled from primary sources in March 2026. All benchmark figures reflect publicly available evaluations as of that date. Projections in Section 4 represent informed extrapolation and should not be taken as predictions.*
