# Speculative Speculative Decoding (SSD) Implementation Plan for llama.cpp

## Executive Summary

This document outlines the implementation plan for integrating Speculative Speculative Decoding (SSD) into llama.cpp to accelerate model inference in the nbchat repository. SSD is a technique that uses a smaller "draft" model to propose multiple tokens, which are then verified by a larger "target" model in parallel, potentially achieving significant speedups.

## Background

### What is SSD?

Speculative Speculative Decoding (SSD) is a technique described in the paper "Speculative Speculative Decoding" (arXiv:2603.03251v2) by Tanishq Kumar. The core idea is:

1. **Draft Model**: A smaller, faster model generates multiple candidate tokens
2. **Target Model**: A larger, more accurate model verifies these candidates in parallel
3. **Acceptance**: Accepted tokens are kept; rejected tokens trigger regeneration

### Key Benefits

- **Speedup**: Can achieve 2-3x speedup in token generation
- **Quality**: Maintains the quality of the target model while leveraging the speed of the draft model
- **Compatibility**: Works with existing llama.cpp infrastructure

## Existing Implementations

### Research Findings

I found an existing implementation by Tanishq Kumar (the paper author) at:
- GitHub: https://github.com/tanishqkumar/ssd
- This is a PyTorch-based implementation that demonstrates the concept

### Implementation Status

The existing implementation is:
- Written in PyTorch with HuggingFace Transformers
- Not directly compatible with llama.cpp (which uses C++ and GGML)
- Focuses on the algorithm rather than low-level optimization

## Implementation Strategy

### Phase 1: Analysis and Planning

#### 1.1 Understand llama.cpp Architecture

Key files to review:
- `llama.cpp/llama.cpp` - Main inference loop
- `llama.cpp/ggml.h` - Core tensor operations
- `llama.cpp/llama-model.h` - Model structure definitions
- `llama.cpp/llama.h` - Public API

#### 1.2 Identify Integration Points

The SSD algorithm needs to integrate at:
- **Token generation loop**: Where draft and target models interact
- **Batch processing**: To parallelize verification
- **Memory management**: To handle multiple model states

### Phase 2: Core Implementation

#### 2.1 Draft Model Integration

**Option A: Separate Draft Model Loading**
```c
struct llama_model *draft_model = llama_model_load_from_file(draft_path);
struct llama_model *target_model = llama_model_load_from_file(target_path);
```

**Option B: Single Model with Speculative Flag**
```c
struct llama_context *ctx = llama_init_from_model(
    target_model, 
    draft_model,  // Optional draft model
    params
);
```

**Recommendation**: Option A provides better flexibility and is easier to implement initially.

#### 2.2 Speculative Decoding Loop

The core algorithm:

```python
# Pseudocode for SSD
def speculative_decode(prompt, draft_model, target_model, draft_tokens=4):
    # Step 1: Draft model generates N tokens
    draft_sequence = draft_model.generate(prompt, draft_tokens)
    
    # Step 2: Target model verifies in parallel
    # This is the key innovation - parallel verification
    acceptance_mask = target_model.verify(prompt + draft_sequence)
    
    # Step 3: Keep accepted tokens, regenerate rejected
    accepted_tokens = [t for t, accepted in zip(draft_sequence, acceptance_mask) if accepted]
    
    # Step 4: If any rejected, target model generates replacement
    if not all(acceptance_mask):
        replacement_tokens = target_model.generate(prompt + accepted_tokens, 1)
        accepted_tokens.extend(replacement_tokens)
    
    return accepted_tokens
```

#### 2.3 Memory Management

**Challenge**: Running two models simultaneously requires careful memory management.

**Solution**:
1. Load draft model first (smaller, fits in VRAM)
2. Load target model (larger, may need CPU offloading)
3. Use `llama_model_quantize` to reduce draft model memory footprint
4. Implement model swapping if VRAM is limited

### Phase 3: llama.cpp Modifications

#### 3.1 API Changes

Add new parameters to `struct llama_context_params`:

```c
struct llama_context_params {
    // ... existing fields ...
    
    // SSD-specific parameters
    struct llama_model *draft_model;  // Optional draft model
    int draft_tokens;                  // Number of draft tokens (default: 4)
    int draft_batch_size;              // Batch size for verification
};
```

#### 3.2 New Functions

```c
// Initialize context with draft model
struct llama_context *llama_init_from_model_with_draft(
    const struct llama_model *model,
    const struct llama_model *draft_model,
    const struct llama_context_params &params
);

// Run speculative decoding step
int llama_decode_speculative(
    struct llama_context *ctx,
    const llama_batch &batch
);
```

#### 3.3 Implementation Details

**File: `llama.cpp`**

1. **Add SSD state to context**:
```c
struct llama_context {
    // ... existing fields ...
    
    // SSD fields
    struct llama_model *draft_model;
    int draft_tokens;
    bool speculative_mode;
};
```

2. **Modify decode loop**:
```c
for (int i = 0; i < n_draft_tokens; i++) {
    // Draft model generates token
    if (ctx->draft_model) {
        std::vector<llama_token> draft_tokens = draft_generate(ctx, i);
        // Target model verifies
        bool accepted = target_verify(ctx, draft_tokens);
        if (accepted) {
            output_tokens.push_back(draft_tokens.back());
        } else {
            // Target model generates replacement
            std::vector<llama_token> replacement = target_generate(ctx);
            output_tokens.push_back(replacement.back());
            break;
        }
    } else {
        // Normal generation
        std::vector<llama_token> token = normal_generate(ctx);
        output_tokens.push_back(token.back());
    }
}
```

### Phase 4: Testing and Validation

#### 4.1 Unit Tests

1. **Draft model loading**: Verify draft model loads correctly
2. **Speculative decoding**: Test with known inputs
3. **Memory usage**: Ensure no memory leaks
4. **Performance**: Measure speedup vs. baseline

#### 4.2 Integration Tests

1. **End-to-end inference**: Full prompt completion
2. **Streaming**: Verify streaming works with SSD
3. **Batch processing**: Test with multiple concurrent requests

#### 4.3 Benchmarking

**Metrics to track**:
- Tokens per second (before/after)
- Memory usage (peak and average)
- Latency (first token, subsequent tokens)
- Acceptance rate (how often draft tokens are accepted)

**Test scenarios**:
- Small draft model (e.g., 1B) with large target (e.g., 7B)
- Medium draft model (e.g., 3B) with large target (e.g., 13B)
- Same model size (for comparison)

### Phase 5: nbchat Integration

#### 5.1 Configuration

Add SSD parameters to `repo_config.yaml`:

```yaml
# SSD Configuration
SSD_ENABLED: true
SSD_DRAFT_MODEL: "unsloth/Qwen3.5-1.5B-GGUF:Q8_0"
SSD_DRAFT_TOKENS: 4
SSD_DRAFT_BATCH_SIZE: 4
```

#### 5.2 Server Integration

Modify `run.py` to support SSD:

```python
def start_llama_server_with_ssd():
    """Start llama-server with SSD enabled."""
    cmd = [
        "./llama-server",
        "-m", TARGET_MODEL_PATH,
        "--draft-model", DRAFT_MODEL_PATH,
        "--draft-n", SSD_DRAFT_TOKENS,
        # ... other parameters
    ]
    # Start server
```

#### 5.3 Monitoring

Add SSD-specific metrics:
- Draft token acceptance rate
- Speedup ratio
- Memory usage comparison

## Implementation Timeline

### Week 1: Foundation
- Day 1-2: Study llama.cpp codebase and SSD paper
- Day 3-4: Create prototype in isolated branch
- Day 5: Initial testing

### Week 2: Core Implementation
- Day 1-3: Implement draft model integration
- Day 4-5: Implement speculative decoding loop

### Week 3: Optimization
- Day 1-2: Memory management optimization
- Day 3-4: Performance tuning
- Day 5: Testing and validation

### Week 4: Integration
- Day 1-2: nbchat integration
- Day 3: Documentation
- Day 4-5: Final testing and deployment

## Risk Assessment

### Technical Risks

1. **Memory Constraints**: Running two models may exceed VRAM
   - Mitigation: Implement model swapping, use smaller draft models

2. **Performance Degradation**: SSD may not always provide speedup
   - Mitigation: Add automatic fallback to normal decoding

3. **Compatibility**: Existing code may break
   - Mitigation: Add feature flags, maintain backward compatibility

### Implementation Risks

1. **Complexity**: SSD adds significant complexity
   - Mitigation: Incremental implementation, extensive testing

2. **Debugging**: Harder to debug speculative failures
   - Mitigation: Add detailed logging, acceptance rate monitoring

## Success Criteria

1. **Performance**: 1.5-2x speedup in token generation
2. **Quality**: No degradation in output quality
3. **Stability**: No crashes or memory leaks
4. **Compatibility**: Works with existing nbchat infrastructure

## Next Steps

1. **Fork llama.cpp**: Create a fork for SSD implementation
2. **Setup Development Environment**: Clone fork, build locally
3. **Implement Core Algorithm**: Start with basic draft + verify
4. **Test Incrementally**: Validate each component before integration
5. **Deploy to nbchat**: Integrate with monitoring and configuration

## References

- Paper: https://arxiv.org/html/2603.03251v2
- Reference Implementation: https://github.com/tanishqkumar/ssd
- llama.cpp: https://github.com/ggerganov/llama.cpp

---

**Document Status**: Draft
**Last Updated**: [Current Date]
**Author**: Assistant
**Reviewers**: Engineering Team