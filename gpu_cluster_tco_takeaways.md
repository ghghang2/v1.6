# Technical Takeaways: How Much Do GPU Clusters Really Cost?

**Source:** [SemiAnalysis — "How Much Do GPU Clusters Really Cost?"](https://newsletter.semianalysis.com/p/how-much-do-gpu-clusters-really-cost) (April 20, 2026)  
**Authors:** Jordan Nanos, Bryan Shan, Cheang Kang Wen, et al.

---

## Executive Summary

SemiAnalysis introduces a comprehensive Total Cost of Ownership (TCO) framework for GPU clusters that goes beyond headline GPU-hour pricing. By analyzing eight cost components — including hidden costs like downtime, setup, and debugging — they demonstrate that **two providers with identical GPU-hour pricing can have dramatically different real TCO**. When GPU pricing is held constant, Gold-tier providers are **5–15% cheaper** than Silver-tier providers for large training workloads, with the gap narrowing to near-zero for fault-tolerant workloads like single-node inference.

---

## 1. The TCO Framework: 8 Cost Components

The article proposes the following TCO formula for GPU clusters (monthly):

```
TCO = GPU + Storage + Network + Control Plane + Support + Goodput + Setup + Debugging
```

| Component | Unit | Description |
|-----------|------|-------------|
| **GPU** | $/GPU-hr | Headline rental price, adjusted for term discounts, volume, spot/preemptible use, and orchestration premiums |
| **Storage** | $/GB-mo | Hot (NVMe parallel FS), warm (object), and cold (archival) storage + data access/egress costs |
| **Networking** | $/hr or $/GB-mo | Frontend/N-S networking: public IPs, firewalls, load balancers, data egress, data transfer |
| **Control Plane** | $/hr | Orchestration software, login/dev nodes, CPU nodes for data processing |
| **Support** | % uplift | Support tier cost (e.g., AWS: 10% down to 3% of bill as spend increases) |
| **Goodput Expense** | % uplift | Hidden cost of downtime — the only metric not on a monthly bill |
| **Setup Expense** | $/hr | Engineering time to provision, configure, and performance-tune the cluster |
| **Debugging Expense** | $/hr | Ongoing engineering time spent debugging cluster issues |

> **Key Insight:** Setup cost is amortized over contract term. Spending weeks setting up a 3-month cluster is expensive; spending weeks on a 3-year cluster is negligible.

---

## 2. The Grand Unifying Theory of Goodput

**Goodput** is defined as the amount of *useful work* completed on a cluster — not all throughput is "good." Bad throughput occurs when GPUs fail, NCCL stalls, or OOM errors occur.

### Goodput Expense Formulas

Three recovery scenarios are modeled:

| Scenario | Formula | Description |
|----------|---------|-------------|
| **Checkpoint-Cold** | `[t_id + t_chkpt/2 + t_init + t_repair] * j_size * #failures * $GPU-hr` | Job waits for cold spare replacement (worst case: hours/days) |
| **Checkpoint-Hot** | `[(t_id + t_chkpt/2 + t_init) * j_size + t_repair * b_radius] * #failures * $GPU-hr` | Job restarts immediately on hot spare node |
| **Fault-Tolerant** | `[(t_id + t_failover) * j_size + t_repair * b_radius] * #failures * $GPU-hr` | Job continues running during hardware failure |

**Variables:**
- `t_id`: Time to identify failure
- `t_chkpt`: Checkpoint frequency
- `t_init`: Job initialization time
- `t_repair`: MTTR (mean time to repair/replace)
- `t_failover`: Time to failover to hot spare
- `b_radius`: Blast radius (e.g., 8-way HGX or 64-way NVL72)
- `j_size`: Average job size
- `#failures`: MTBF (mean time between failures)

### MTBF Benchmarks (GPU-level)

| Provider Tier | MTBF |
|---------------|------|
| Gold-tier | ~25,000 GPU-hr |
| Hyperscaler | ~25,000 GPU-hr |
| Silver-tier | ~15,000 GPU-hr (60% worse) |

---

## 3. Fault Tolerance Frameworks Compared

| Framework | Type | Blast Radius | Performance Overhead | Memory Overhead | Cost |
|-----------|------|--------------|---------------------|-----------------|------|
| **TorchFT** (Meta) | Open-source | Entire replica group (FSDP shard) | >10% (uses GLOO vs NCCL) | None | Free |
| **AWS HyperPod Checkpointless** | AWS-only | Replica group | None | ~1 DCP checkpoint size per redundant replica | Included |
| **Clockwork TorchPass** | Licensed | Configurable | None | None | License fee |

**Recovery Time Comparison:**
- Checkpointless Training: **1 min 45 sec**
- Checkpoint Restart: **15 minutes**
- Deep health check detection: **<2 minutes**
- Node replacement: **<20 minutes** (Gold-tier/Hyperscaler) vs **1 hour** (Silver-tier)

> **Note:** TorchFT's blast radius equals the FSDP shard size. With shard=16, one GPU failure takes out 16 GPUs. With shard=32, it takes out 32 GPUs.

---

## 4. Provider Tier Classifications (ClusterMAX 2.1)

| Tier | Examples | Characteristics |
|------|----------|----------------|
| **Gold-tier** | Nebius, Fluidstack, Crusoe | Aggressive discounts (~25th percentile), strong storage, InfiniBand/RoCE out-of-box, free POCs, 24x7 direct engineer support, hot-spare pools with capacity guarantees, monitoring by default |
| **Hyperscaler** | Oracle, Azure, AWS, GCP | Moderate discounts (50th–75th percentile), poor default storage performance, EFA tuning required, paid POCs, premium support (3–10% of bill), health checks available, hot spares available |
| **Silver-tier** | Together, Lambda, Vultr, Voltage Park, Cirrascale, Gcore, Firmus, GMO, Tensorwave | Variable pricing (below 25th to 50th percentile), mixed storage quality, good IB/RoCEv2 out-of-box, POCs not always free, limited 24x7 support, cold spares typical, no capacity guarantees |

**Hot Spare Pool Sizing:** Top-tier providers maintain **2–6% of nodes** in a hot-spare pool for multi-tenant clusters at 4,000+ GPU scale.

---

## 5. Three Scenarios Analyzed

### Scenario 1: Large LLM Pretrain

**Configuration:** 5,184 GB300 NVL72 GPUs ($4/GPU-hr), 500 TB hot storage, 10 PB cold storage, 2 TB/GPU ratio

| Cost Component | Gold-tier | Hyperscaler | Silver-tier |
|----------------|-----------|-------------|-------------|
| **TCO Multiplier** | 1.0x (baseline) | 1.10x | 1.15x |
| **Goodput Expense** | 6.14% | 10.53% | 20.91% |

**Key Findings:**
- Hyperscaler's 10% premium driven by support costs and EFA tuning setup time
- Silver-tier's 15% premium driven by goodput loss (downtime), setup time, and storage
- Silver-tier has 60% worse MTBF, 4x longer failure identification (1 hr vs 15 min), and 4x longer repair time (1 hr vs 15 min)
- Job init time: 10 min (Gold/Hyperscaler) vs 15 min (Silver-tier, due to worse storage)

### Scenario 2: Multimodal RL Research

**Configuration:** 2,048 B200 GPUs, 25 PB hot storage, 12 TB/GPU ratio, small jobs, no fault tolerance

| Provider | GPU Price | TCO Multiplier | Goodput Expense |
|----------|-----------|----------------|-----------------|
| Gold-tier (25th %ile) | $2.40/GPU-hr | 1.0x | 0.23% |
| Hyperscaler (50th %ile) | $3.10/GPU-hr | 1.61x | 0.96% |
| Silver-tier (25th %ile) | $2.40/GPU-hr | 1.15x | ~0.5% |

**Key Findings:**
- Hyperscaler is **61% more expensive** due to GPU pricing, orchestration premiums, storage, and setup
- Goodput differences are small (0.23%–0.96%) because small jobs are less impacted by failures
- Average job size: 64 GPUs (3% of cluster), async checkpoint every 1 hour

### Scenario 3: Inference Endpoints

**Configuration:** 512 H200 GPUs, 500 TB hot storage, 1 TB/GPU ratio, single-node jobs (8 GPUs each), fault-tolerant serving

| Provider | TCO Multiplier | Goodput Expense |
|----------|----------------|-----------------|
| Gold-tier | 1.0x | ~0.5% |
| Hyperscaler | 1.59x | ~0.5% |
| Silver-tier | 1.0x (equal GPU price) | ~0.5% |

**Key Findings:**
- TCO difference is driven **almost entirely by GPU pricing** (<1% difference at equal GPU price)
- Goodput expense is negligible (~0.5%) for all tiers because inference frameworks (llm-d, SGLang OME) handle failures via load balancer retries
- Silver-tier can tolerate **8-hour repair times** for single-node inference without impacting goodput
- **Conclusion:** Lower-tier providers can effectively serve single-node inference workloads using unused capacity globally

---

## 6. Storage Considerations

| Parameter | Range | Notes |
|-----------|-------|-------|
| Storage ratio (low) | 2 TB/GPU | Training clusters |
| Storage ratio (high) | 25 TB/GPU | Research workloads |
| AWS FSx for Lustre tiers | 125 MB/s/TiB to 1,000 MB/s/TiB | 4x throughput costs ~3x more |
| Hot storage types | Weka, Lustre, VAST | Performance varies significantly between providers |

> **Key Insight:** Storage performance directly impacts job initialization time (10 min vs 15 min), which compounds across failures in the goodput calculation.

---

## 7. Engineering Cost Assumptions

| Item | Assumed Cost |
|------|-------------|
| Engineer salary | $200,000 USD/year |
| Hyperscaler POC (Scenario 1) | 1 month paid |
| Silver-tier POC (Scenario 2) | 2 weeks paid |
| Ongoing debugging (Hyperscaler) | 1 week/month per engineer |

---

## 8. Key Numerical Benchmarks Summary

| Metric | Value | Context |
|--------|-------|---------|
| Gold-tier vs Silver-tier TCO gap | 5–15% | At equal GPU pricing, large training workloads |
| Hyperscaler vs Gold-tier TCO gap | ~10% | At equal GPU pricing |
| Fault-tolerant workload TCO gap | ~0% | Single-node inference clusters |
| Top-tier spare pool | 2–6% | Of total nodes |
| GPU MTBF (Gold/Hyperscaler) | ~25,000 GPU-hr | |
| GPU MTBF (Silver-tier) | ~15,000 GPU-hr | 60% worse |
| Failure detection (Gold/Hyperscaler) | 15 minutes | |
| Failure detection (Silver-tier) | 1 hour | 4x slower |
| Node repair (Gold/Hyperscaler) | 15 minutes | |
| Node repair (Silver-tier) | 1 hour | 4x slower |
| Checkpointless recovery time | 1 min 45 sec | AWS HyperPod |
| Checkpoint restart recovery time | 15 minutes | Traditional approach |
| TorchFT performance overhead | >10% | Due to GLOO vs NCCL |
| Hyperscaler support cost | 3–10% | Of monthly bill |
| B200 pricing (Aug 2025) | $2.40 (25th %ile) / $3.10 (50th %ile) | Neocloud vs Hyperscaler |

---

## 9. Strategic Implications

1. **GPU-hour pricing is misleading:** Two providers with identical headline pricing can have very different TCO once downtime, setup, and debugging are accounted for.

2. **Workload size matters:** Larger jobs on larger clusters are exponentially more impacted by individual failures. The blast radius and MTBF interact to determine goodput loss.

3. **Fault tolerance is workload-dependent:**
   - Large pretraining jobs: Need fault-tolerant frameworks (TorchFT, checkpointless, TorchPass)
   - Small research jobs: Checkpoint restart is sufficient; provider reliability matters less
   - Inference: Native framework fault tolerance makes provider reliability largely irrelevant

4. **Silver-tier providers are viable for inference:** With fault-tolerant serving frameworks, lower-tier providers can effectively serve single-node inference workloads at lower cost.

5. **Setup cost amortization matters:** A 3-year contract absorbs setup costs; a 3-month contract makes setup time a significant expense.

6. **Storage performance is a hidden differentiator:** Storage throughput directly impacts job init time, which compounds across failures in large training jobs.

---

## 10. Limitations and Future Work

- Pricing data is a snapshot from **August 2025** (prices are trending upward)
- MTBF data is based on estimated inputs; real-world data collection is planned for ClusterMAX 3.0
- Fault-tolerant training frameworks are still immature; only TorchFT is open-source
- The analysis covers three representative scenarios; actual TCO will vary by workload specifics

---

*Generated from SemiAnalysis article "How Much Do GPU Clusters Really Cost?" (April 2026). All numbers and references sourced directly from the article.*
