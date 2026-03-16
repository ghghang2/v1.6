ggml_cuda_init: found 1 CUDA devices:
  Device 0: Tesla T4, compute capability 7.5, VMM: yes
| model                          |       size |     params | backend    | ngl | n_batch | n_ubatch |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -------: | --------------: | -------------------: |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |      512 |           pp512 |        904.96 ± 1.98 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |      512 |           tg128 |         24.12 ± 0.09 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |     1024 |           pp512 |        879.53 ± 1.28 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |     1024 |           tg128 |         23.78 ± 0.08 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |     2048 |           pp512 |        859.58 ± 2.91 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |     2048 |           tg128 |         23.50 ± 0.10 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |     4096 |           pp512 |        842.30 ± 2.13 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |     4096 |           tg128 |         23.10 ± 0.10 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    1024 |      512 |           pp512 |        829.44 ± 1.16 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    1024 |      512 |           tg128 |         22.77 ± 0.13 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    1024 |     1024 |           pp512 |        820.14 ± 1.37 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    1024 |     1024 |           tg128 |         22.48 ± 0.12 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    1024 |     2048 |           pp512 |        808.58 ± 4.37 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    1024 |     2048 |           tg128 |         21.92 ± 0.15 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    1024 |     4096 |           pp512 |        800.04 ± 4.29 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    1024 |     4096 |           tg128 |         21.31 ± 0.15 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    2048 |      512 |           pp512 |        793.60 ± 0.98 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    2048 |      512 |           tg128 |         20.89 ± 0.16 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    2048 |     1024 |           pp512 |        793.00 ± 1.01 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    2048 |     1024 |           tg128 |         20.42 ± 0.06 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    2048 |     2048 |           pp512 |        791.93 ± 0.77 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    2048 |     2048 |           tg128 |         20.41 ± 0.16 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    2048 |     4096 |           pp512 |        792.08 ± 0.53 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    2048 |     4096 |           tg128 |         19.86 ± 0.04 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    4096 |      512 |           pp512 |        790.79 ± 1.50 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    4096 |      512 |           tg128 |         19.85 ± 0.02 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    4096 |     1024 |           pp512 |        792.09 ± 0.88 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    4096 |     1024 |           tg128 |         19.84 ± 0.02 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    4096 |     2048 |           pp512 |        790.28 ± 0.76 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    4096 |     2048 |           tg128 |         19.82 ± 0.02 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    4096 |     4096 |           pp512 |        788.53 ± 5.04 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |    4096 |     4096 |           tg128 |         19.81 ± 0.05 |

build: ecd99d6a9 (8193)

ggml_cuda_init: found 1 CUDA devices:
  Device 0: Tesla T4, compute capability 7.5, VMM: yes
| model                          |       size |     params | backend    | ngl | n_batch |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | --------------: | -------------------: |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |           pp512 |        924.09 ± 2.11 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |          pp4096 |        883.24 ± 6.03 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |          pp8192 |        822.86 ± 9.70 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |         pp16384 |       726.62 ± 11.91 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |         pp32768 |        584.27 ± 4.90 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |           tg128 |         19.71 ± 0.11 |

build: ecd99d6a9 (8193)

ggml_cuda_init: found 1 CUDA devices:
  Device 0: Tesla T4, compute capability 7.5, VMM: yes
| model                          |       size |     params | backend    | ngl | n_batch | fa | mmap |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -: | ---: | --------------: | -------------------: |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  0 |    0 |           pp512 |        915.85 ± 2.17 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  0 |    0 |           tg128 |         24.24 ± 0.10 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  1 |    0 |           pp512 |        892.11 ± 1.44 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  1 |    0 |           tg128 |         23.94 ± 0.13 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  0 |    1 |           pp512 |        855.43 ± 2.50 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  0 |    1 |           tg128 |         23.34 ± 0.14 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  1 |    1 |           pp512 |        837.34 ± 4.05 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  1 |    1 |           tg128 |         22.48 ± 0.50 |

build: ecd99d6a9 (8193)


ggml_cuda_init: found 1 CUDA devices:
  Device 0: Tesla T4, compute capability 7.5, VMM: yes
| model                          |       size |     params | backend    | ngl | n_batch |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | --------------: | -------------------: |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |           pp512 |        898.77 ± 1.82 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |           tg128 |         24.05 ± 0.11 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |   pp512 @ d4096 |        800.82 ± 2.92 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |   tg128 @ d4096 |         22.86 ± 0.20 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  pp512 @ d16384 |        598.60 ± 8.10 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  tg128 @ d16384 |         15.11 ± 0.51 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  pp512 @ d32768 |        446.47 ± 5.20 |
| qwen35 ?B Q8_0                 |   8.86 GiB |     8.95 B | CUDA       |  99 |     512 |  tg128 @ d32768 |         12.70 ± 0.30 |

build: ecd99d6a9 (8193)

ballpark for fa 1, ctk/ctv q8
prompt eval time =     388.66 ms /   196 tokens (    1.98 ms per token,   504.29 tokens per second)
       eval time =    2286.82 ms /    44 tokens (   51.97 ms per token,    19.24 tokens per second)
      total time =    2675.48 ms /   240 tokens

      