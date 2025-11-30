# OpenEvolve Actors & Customization Guide

Complete breakdown of all actors in the OpenEvolve system and how to customize them for AMD gfx906 kernel optimization.

---

## 🎭 The Seven Main Actors

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPENEVOLVE ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐                                              │
│   │ 1. CONTROLLER│ ← Main orchestrator                         │
│   └──────┬──────┘                                              │
│          │                                                      │
│          ├──────► ┌─────────────┐                              │
│          │        │ 2. DATABASE  │ ← MAP-Elites storage        │
│          │        └─────────────┘                              │
│          │                                                      │
│          ├──────► ┌─────────────┐                              │
│          │        │ 3. LLM       │ ← Claude via CLI bridge     │
│          │        │ ENSEMBLE     │                             │
│          │        └─────────────┘                              │
│          │                                                      │
│          ├──────► ┌─────────────┐                              │
│          │        │ 4. PROMPT    │ ← Builds prompts for Claude │
│          │        │ SAMPLER      │                             │
│          │        └─────────────┘                              │
│          │                                                      │
│          ├──────► ┌─────────────┐                              │
│          │        │ 5. EVALUATOR │ ← Tests & scores programs   │
│          │        └─────────────┘                              │
│          │                                                      │
│          ├──────► ┌─────────────┐                              │
│          │        │ 6. ITERATION │ ← Single evolution step     │
│          │        │ WORKER       │                             │
│          │        └─────────────┘                              │
│          │                                                      │
│          └──────► ┌─────────────┐                              │
│                   │ 7. CONFIG    │ ← YAML settings             │
│                   │ SYSTEM       │                             │
│                   └─────────────┘                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ CONTROLLER (openevolve/controller.py)

### **What It Does**

The main orchestrator that runs the evolution loop:

```python
for iteration in range(max_iterations):
    1. Database.sample()       # Pick parent + inspirations
    2. PromptSampler.build()   # Create prompt
    3. LLM.generate()          # Get optimized code
    4. Evaluator.evaluate()    # Test & score
    5. Database.add()          # Store if good
```

### **Key Responsibilities**

- Manages iteration loop (0 → max_iterations)
- Coordinates all other actors
- Handles checkpoints (save/resume)
- Tracks best program globally
- Logs progress

### **What You Can Customize**

**In `config.yaml`:**

```yaml
max_iterations: 1200          # How many evolution steps
checkpoint_interval: 50       # Save every N iterations
random_seed: 42              # Reproducibility (optional)
log_level: "INFO"            # DEBUG, INFO, WARNING
```

**For AMD gfx906:**
- `max_iterations: 1200-2000` - More iterations for complex kernels
- `checkpoint_interval: 50` - Frequent saves (kernel compilation is slow)

### **What You Shouldn't Change**

- The core loop logic (unless you know what you're doing)
- Process pool management
- Checkpoint format

---

## 2️⃣ DATABASE (openevolve/database.py)

### **What It Does**

Stores evolved programs using **MAP-Elites algorithm** with **islands**:

```
┌──────────────────────────────────────────────────┐
│             MAP-ELITES GRID (per island)         │
├──────────────────────────────────────────────────┤
│                                                  │
│        Complexity →                              │
│    ┌────┬────┬────┬────┬────┐                  │
│ D  │ A  │ B  │    │ D  │    │  Each cell holds │
│ i  ├────┼────┼────┼────┼────┤  BEST program    │
│ v  │    │ C  │ E  │    │ F  │  for that        │
│ e  ├────┼────┼────┼────┼────┤  feature combo   │
│ r  │ G  │    │ H  │    │    │                  │
│ s  ├────┼────┼────┼────┼────┤  Maintains       │
│ i  │    │ I  │    │ J  │    │  DIVERSITY       │
│ t  ├────┼────┼────┼────┼────┤                  │
│ y  │ K  │    │ L  │    │ M  │                  │
│ ↓  └────┴────┴────┴────┴────┘                  │
└──────────────────────────────────────────────────┘

Multiple islands (default: 4) evolve independently
Occasional migration prevents convergence
```

### **Key Concepts**

**1. Feature Dimensions**

Programs are mapped to cells based on features:
- **complexity**: Code length (characters)
- **diversity**: Edit distance from parent
- **custom**: Your own metrics (e.g., register usage)

**2. Islands**

Multiple isolated populations:
- Prevent premature convergence
- Explore different optimization strategies
- Migrate best programs occasionally

**3. Sampling Strategies**

When picking a parent:
- **Elite sampling** (70%): Pick from best programs
- **Diversity sampling** (30%): Pick from diverse cells
- Always includes global best as inspiration

### **What You Can Customize**

**In `config.yaml`:**

```yaml
database:
  population_size: 100         # Total programs across all islands
  archive_size: 50             # Elite programs to keep
  num_islands: 4               # Parallel populations

  # Feature dimensions for MAP-Elites grid
  feature_dimensions:
    - "complexity"             # Built-in: code length
    - "diversity"              # Built-in: edit distance
    - "register_usage"         # Custom: from your evaluator!

  # Bins per dimension
  feature_bins:
    complexity: 10             # 10 complexity levels
    diversity: 10              # 10 diversity levels
    register_usage: 8          # 8 register usage buckets

  # Sampling behavior
  elite_selection_ratio: 0.3   # 30% elite, 70% diverse
  exploitation_ratio: 0.7      # 70% best, 30% exploratory

  # Island management
  migration_interval: 20       # Migrate every 20 generations
  migration_rate: 0.1          # 10% of programs migrate
```

**For AMD gfx906 Kernel Optimization:**

```yaml
database:
  population_size: 120         # Larger for complex kernels
  num_islands: 5               # More parallel exploration

  feature_dimensions:
    - "complexity"
    - "diversity"
    - "register_pressure"      # VGPRs used (from evaluator)
    - "memory_efficiency"      # L2 hit rate (from evaluator)
    - "occupancy"              # Wavefront occupancy

  feature_bins:
    complexity: 12             # Fine-grained code size
    diversity: 10
    register_pressure: 8       # 8 VGPR usage levels
    memory_efficiency: 10      # 10 L2 hit rate buckets
    occupancy: 6               # 6 occupancy levels

  migration_interval: 25       # Migrate less frequently
  migration_rate: 0.15         # More aggressive migration
```

**Custom Features from Evaluator:**

Your evaluator returns metrics like:
```python
metrics = {
    "combined_score": 48.5,
    "register_pressure": 64,    # VGPRs per thread
    "memory_efficiency": 85.2,  # L2 hit rate %
    "occupancy": 0.75          # Wavefront occupancy
}
```

Database automatically bins these into grid cells!

### **Advanced: Custom Sampling**

You can modify `database.sample()` logic if needed, but the default is usually good.

---

## 3️⃣ LLM ENSEMBLE (openevolve/llm/ensemble.py)

### **What It Does**

Manages calls to Claude (via your CLI bridge):

```
┌────────────────────────────────────────────┐
│        LLM ENSEMBLE                        │
├────────────────────────────────────────────┤
│                                            │
│  Primary Model: claude-code-cli (80%)     │
│  │                                         │
│  ├──► CLI Bridge ──► claude-code process  │
│  │                                         │
│  └──► Retry on failure (3x)               │
│                                            │
│  Secondary Model: (optional, 20%)         │
│  └──► Fallback if primary fails           │
│                                            │
└────────────────────────────────────────────┘
```

### **What You Can Customize**

**In `config.yaml`:**

```yaml
llm:
  # Primary model (your CLI bridge)
  primary_model: "claude-code-cli"
  primary_model_weight: 1.0         # 100% of requests

  # API endpoint
  api_base: "http://localhost:8000/v1"  # CLI bridge URL
  api_key: "not-needed"

  # Generation parameters
  temperature: 0.8                  # Creativity (0.0-1.0)
  top_p: 0.95                       # Nucleus sampling
  max_tokens: 8192                  # Response length
  timeout: 600                      # 10 minutes (CLI can be slow)

  # Retry logic
  retries: 3                        # Retry failed calls
  retry_delay: 5                    # Wait 5s between retries
```

**For AMD gfx906:**

```yaml
llm:
  temperature: 0.85              # Slightly higher for creative HIP optimizations
  max_tokens: 12288              # HIP kernels can be verbose
  timeout: 900                   # 15 minutes (rocprof is slow)
```

**Temperature Guide:**

- `0.3-0.5`: Conservative, incremental changes
- `0.6-0.8`: Balanced creativity (recommended)
- `0.9-1.0`: Very creative, experimental (risky)

### **Advanced: Model Ensemble**

You can use multiple models (though limited with CLI):

```yaml
llm:
  primary_model: "claude-sonnet-4.5"
  primary_model_weight: 0.7
  secondary_model: "claude-opus-4"
  secondary_model_weight: 0.3
```

70% requests → Sonnet, 30% → Opus (more powerful, slower)

**Note:** With CLI bridge, you're limited to one Claude instance.

---

## 4️⃣ PROMPT SAMPLER (openevolve/prompt/sampler.py)

### **What It Does**

Builds the prompt that Claude sees:

```
┌──────────────────────────────────────────────────────┐
│  PROMPT STRUCTURE                                    │
├──────────────────────────────────────────────────────┤
│                                                      │
│  [SYSTEM MESSAGE]                                    │
│  You are an expert HIP programmer...                 │
│  Target: AMD gfx906 (64-thread wavefronts)          │
│  Optimize for: L2 cache hit rate, occupancy...      │
│                                                      │
│  [USER MESSAGE]                                      │
│  Current kernel (score: 45.2):                       │
│  [Full kernel code - 500 lines]                      │
│                                                      │
│  Performance metrics:                                │
│  - Duration: 3250ns                                  │
│  - L2 Hit Rate: 78.5%                               │
│  - Occupancy: 62.3%                                 │
│  - Register Pressure: 64 VGPRs                      │
│                                                      │
│  Artifacts from last run:                           │
│  - Warning: Bank conflicts detected in LDS          │
│  - rocprof: High VALU stall cycles                 │
│                                                      │
│  Top performing kernels:                            │
│  1. Score 47.9: Uses prefetching [snippet]         │
│  2. Score 46.8: Reduced divergence [snippet]       │
│  3. Score 46.1: Better vectorization [snippet]     │
│                                                      │
│  Improve this kernel to increase the score.         │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### **What You Can Customize**

**In `config.yaml`:**

```yaml
prompt:
  # System message (THE MOST IMPORTANT SETTING!)
  system_message: |
    You are an expert HIP programmer specializing in AMD GPU optimization.

    # TARGET HARDWARE
    - GPU: AMD gfx906 (Vega 20 architecture)
    - Wavefront size: 64 threads (NOT 32 like NVIDIA!)
    - Local Data Share: 64 KB per compute unit
    - VGPRs: 256 per thread maximum
    - Compute Units: 60

    # OPTIMIZATION GOALS
    Primary: Minimize execution time
    Secondary metrics:
    - L2 cache hit rate (higher is better)
    - Wavefront occupancy (higher is better)
    - VALU utilization (higher is better)
    - Register pressure (lower is better)
    - LDS bank conflicts (lower is better)

    # WHAT YOU CAN CHANGE
    ✅ Memory access patterns
    ✅ Vectorization strategies
    ✅ LDS usage and indexing
    ✅ Loop unrolling
    ✅ Wavefront-level cooperation

    # WHAT YOU CANNOT CHANGE
    ❌ Kernel function signature
    ❌ Algorithm correctness
    ❌ External API compatibility

    # HIP-SPECIFIC NOTES
    - Use __syncthreads() or wavefront intrinsics
    - 64-thread wavefronts require different indexing
    - LDS banking rules differ from CUDA shared memory
    - Prefer vectorized loads (float4, etc.)

    Output the complete optimized kernel in HIP.

  # How many top programs to show Claude
  num_top_programs: 3

  # Include error messages from failed runs
  include_artifacts: true
  max_artifact_bytes: 8192

  # Template randomization (adds variation)
  use_template_stochasticity: true
```

### **System Message is CRITICAL!**

This is where you encode your domain knowledge:

**Bad system message:**
```
You are a programmer. Make the code faster.
```

**Good system message:**
```
You are an AMD HIP expert targeting gfx906.

KEY FACTS:
- 64-thread wavefronts (not 32!)
- 256 VGPRs per thread max
- L2 cache: 4MB, 64-byte lines
- Memory coalescing: 64-byte aligned

COMMON OPTIMIZATIONS:
1. Vectorized loads: Use float4 for coalescing
2. LDS usage: Avoid bank conflicts (32 banks)
3. Occupancy: Balance registers vs occupancy
4. Divergence: Minimize with uniform control flow

METRICS TO OPTIMIZE:
- Duration (primary)
- L2 hit rate (shows memory efficiency)
- VALU utilization (shows compute efficiency)
- Occupancy (shows parallelism)

CONSTRAINTS:
- Kernel signature must not change
- Must pass correctness tests
- Must compile with hipcc
```

**Iterative Refinement:**

Your system message should evolve as you learn what works:

1. **Run 20 iterations** with basic message
2. **Observe** what Claude tries (check logs)
3. **Add guidance** for mistakes you see:
   - "Don't reduce thread count - hurts occupancy"
   - "Always check alignment for vectorized loads"
4. **Run 20 more** iterations
5. **Repeat** until Claude understands your domain

---

## 5️⃣ EVALUATOR (Your evaluator.py)

### **What It Does**

**THE MOST IMPORTANT ACTOR for your use case!**

```python
def evaluate(program_path: str) -> EvaluationResult:
    """
    1. Load kernel from program_path
    2. Write to llama.cpp source tree
    3. Compile with hipcc
    4. Run correctness tests
    5. Profile with rocprof
    6. Calculate score from metrics
    7. Return EvaluationResult
    """
```

### **Current Evaluator (CUDA-based)**

Your current evaluator:
- Writes to `.cu` file (CUDA)
- Compiles with `nvcc`
- Profiles with `ncu` (Nsight Compute)
- Returns NVIDIA-specific metrics

**Location:** `examples/cuda_solve_tri_opt/evaluator.py`

### **What You MUST Customize for AMD gfx906**

**1. File Paths**

```python
# CURRENT (Windows + CUDA):
llama_cpp_root = r"F:\Users\timbe\Desktop\test optimization"
target_kernel_file = r"ggml\src\ggml-cuda\solve_tri.cu"
test_executable = r"bin\Release\test-backend-ops.exe"

# NEEDED (Linux + HIP):
llama_cpp_root = "/home/user/llama.cpp"
target_kernel_file = "ggml/src/ggml-hip/solve_tri.hip"
test_executable = "bin/test-backend-ops"
```

**2. Build System**

```python
# CURRENT (CUDA):
config_cmd = ["cmake", "-B", "build", "-DCMAKE_CUDA_FLAGS=-lineinfo"]

# NEEDED (HIP):
config_cmd = [
    "cmake", "-B", "build",
    "-DGGML_HIP=ON",
    "-DCMAKE_HIP_COMPILER=hipcc"
]
```

**3. Profiling**

```python
# CURRENT (Nsight Compute):
ncu_cmd = [
    "ncu",
    "--csv",
    "--set", "full",
    "--launch-count", "50",
    test_executable, "perf", "-o", "SOLVE_TRI"
]

# NEEDED (rocprof):
rocprof_cmd = [
    "rocprof",
    "--stats",
    "--timestamp", "on",
    "--basenames", "on",
    test_executable, "perf", "-o", "SOLVE_TRI"
]
```

**4. Metrics Parsing**

```python
# CURRENT (NVIDIA metrics):
METRICS_CONFIG = {
    "L2 Hit Rate": {...},
    "Compute (SM) Throughput": {...},
    "Eligible Warps Per Scheduler": {...},
    # ... 10 more NVIDIA-specific metrics
}

# NEEDED (AMD metrics):
METRICS_CONFIG = {
    "Duration": {
        "weight": 5.0,
        "higher_is_better": False
    },
    "L2CacheHit": {
        "weight": 3.0,
        "higher_is_better": True
    },
    "VALUUtilization": {
        "weight": 2.5,
        "higher_is_better": True
    },
    "LDSBankConflict": {
        "weight": 2.0,
        "higher_is_better": False
    },
    "WavefrontOccupancy": {
        "weight": 2.0,
        "higher_is_better": True
    },
    "VGPRs": {
        "weight": 1.5,
        "higher_is_better": False
    },
    # ... more AMD GCN metrics
}
```

**5. Score Calculation**

The current evaluator uses a weighted logarithmic formula:

```python
def calculate_combined_score(metrics):
    score = 0
    for name, config in METRICS_CONFIG.items():
        val = metrics.get(name, 0.000001)
        term = config["weight"] * math.log10(val)

        if config["higher_is_better"]:
            score += term
        else:
            score -= term

    return score + 50  # Offset for positive scores
```

**For AMD gfx906, you'll need:**
- Different metric names (from rocprof)
- Different weights (what matters for gfx906)
- Possibly different formula

### **Custom Metrics for Database**

Return any metrics you want as features:

```python
return EvaluationResult(
    metrics={
        "combined_score": 48.5,      # Required: overall score

        # These become features for MAP-Elites:
        "register_pressure": 64,      # VGPRs used
        "memory_efficiency": 85.2,    # L2 hit rate
        "occupancy": 0.75,           # Wavefront occupancy
        "valu_util": 68.3,           # Vector ALU usage
        "lds_conflicts": 12,         # Bank conflicts
        "duration_ns": 2980,         # Execution time
    },
    artifacts={
        "rocprof_output": rocprof_csv,  # Full profiling data
        "build_warnings": build_stderr,  # Compilation warnings
    }
)
```

Database will use these for grid dimensions!

---

## 6️⃣ ITERATION WORKER (openevolve/iteration.py)

### **What It Does**

Executes a single evolution step:

```python
async def run_iteration(iteration_num):
    # 1. Sample parent from database
    parent, inspirations = database.sample()

    # 2. Build prompt
    prompt = prompt_sampler.build(
        current_program=parent.code,
        program_metrics=parent.metrics,
        inspirations=inspirations
    )

    # 3. Generate mutation via LLM
    llm_response = await llm.generate(prompt)

    # 4. Parse new code
    child_code = parse_code(llm_response)

    # 5. Evaluate
    child_metrics = await evaluator.evaluate(child_code)

    # 6. Store in database
    database.add(child_program)
```

### **What You Can Customize**

**Evolution Mode:**

```yaml
# Diff-based (incremental changes)
diff_based_evolution: true
allow_full_rewrites: false

# Full rewrite (complete kernel regeneration)
diff_based_evolution: false
allow_full_rewrites: true
```

**For HIP kernels:**
- Start with `diff_based_evolution: true` (safer)
- Switch to `allow_full_rewrites: true` if stuck (more exploration)

### **What You Shouldn't Change**

The iteration logic is well-optimized. Don't modify unless you have a specific reason.

---

## 7️⃣ CONFIG SYSTEM (config.yaml)

### **What It Does**

Central configuration for all actors:

```yaml
# Controller settings
max_iterations: 1200
checkpoint_interval: 50
random_seed: 42

# LLM settings
llm:
  primary_model: "claude-code-cli"
  api_base: "http://localhost:8000/v1"
  temperature: 0.8
  ...

# Database settings
database:
  population_size: 100
  num_islands: 4
  feature_dimensions: [...]
  ...

# Prompt settings
prompt:
  system_message: |
    You are an expert...
  num_top_programs: 3
  ...

# Evaluator settings
evaluator:
  timeout: 120
  parallel_evaluations: 1
  ...

# Evolution settings
diff_based_evolution: true
max_code_length: 20000
```

### **Complete AMD gfx906 Config Template**

See next section for full example...

---

## 🎯 Complete Config for AMD gfx906

```yaml
# AMD gfx906 HIP Kernel Optimization Config
max_iterations: 1500
checkpoint_interval: 50
log_level: "INFO"
random_seed: 42  # For reproducibility

# LLM Configuration (CLI Bridge)
llm:
  primary_model: "claude-code-cli"
  primary_model_weight: 1.0
  api_base: "http://localhost:8000/v1"
  api_key: "not-needed"
  temperature: 0.85        # Slightly creative
  top_p: 0.95
  max_tokens: 12288        # HIP kernels can be long
  timeout: 900             # 15 min (rocprof is slow)
  retries: 3
  retry_delay: 10

# Prompt Configuration
prompt:
  system_message: |
    You are an expert HIP programmer specializing in AMD gfx906 GPU optimization.

    # TARGET HARDWARE: AMD gfx906 (Vega 20 Architecture)
    - Wavefront size: 64 threads (NOT 32 like NVIDIA!)
    - VGPRs: 256 per thread maximum
    - SGPRs: 102 per wavefront
    - LDS (Local Data Share): 64 KB per compute unit (32 banks)
    - L2 Cache: 4 MB (64-byte lines)
    - Compute Units: 60
    - Memory bandwidth: ~1 TB/s (HBM2)

    # OPTIMIZATION GOALS (in priority order)
    1. PRIMARY: Minimize kernel execution time (duration_ns)
    2. L2 cache hit rate (target: >85%)
    3. Wavefront occupancy (target: >0.75)
    4. VALU utilization (target: >70%)
    5. Minimize register pressure (keep VGPRs <200)
    6. Minimize LDS bank conflicts

    # KERNEL CONTEXT: solve_tri for llama.cpp
    - Solves triangular systems (Ax = b)
    - Matrix size: typically 64x64
    - Used in Mamba attention mechanism
    - Currently CUDA-based, porting to HIP

    # HIP PROGRAMMING GUIDELINES

    ## Memory Access
    - Coalescing: Align to 64 bytes, use float4 for vectorization
    - LDS banking: 32 banks, 4-byte stride avoids conflicts
    - Prefetching: Load data early to hide latency

    ## Wavefront Programming
    - 64 threads per wavefront (adjust all indexing!)
    - Use __builtin_amdgcn_wave_* intrinsics
    - Avoid divergence (if/else with different threads)

    ## Register Management
    - Fewer VGPRs = higher occupancy
    - Prefer recomputation over storage if cheap
    - Use compiler hints: __launch_bounds__

    ## LDS (Shared Memory) Usage
    - 32 banks (different from CUDA's banking)
    - Bank conflicts when threads access different words in same bank
    - Padding can help avoid conflicts

    # COMMON PITFALLS TO AVOID
    ❌ Don't assume 32-thread warps (it's 64!)
    ❌ Don't use CUDA intrinsics (__syncwarp doesn't exist)
    ❌ Don't ignore alignment (causes poor coalescing)
    ❌ Don't use too many VGPRs (kills occupancy)

    # WHAT YOU CAN MODIFY
    ✅ Memory access patterns and indexing
    ✅ Loop structure and unrolling
    ✅ LDS usage and layout
    ✅ Vectorization (float4, etc.)
    ✅ Wavefront-level optimizations
    ✅ Register allocation strategies

    # WHAT YOU MUST NOT CHANGE
    ❌ Kernel function signature
    ❌ Algorithm correctness (must solve Ax = b correctly)
    ❌ External API (how kernel is called)

    # OUTPUT FORMAT
    Provide the complete optimized HIP kernel code.
    Include the EVOLVE-BLOCK markers.
    Ensure code compiles with hipcc.

  num_top_programs: 3
  include_artifacts: true
  max_artifact_bytes: 16384
  use_template_stochasticity: true

# Database Configuration (MAP-Elites + Islands)
database:
  population_size: 150         # Larger for complex search
  archive_size: 60             # More elites
  num_islands: 5               # More parallel exploration

  # Multi-dimensional feature space
  feature_dimensions:
    - "complexity"             # Built-in: code length
    - "diversity"              # Built-in: edit distance
    - "register_pressure"      # Custom: VGPRs used
    - "memory_efficiency"      # Custom: L2 hit rate
    - "occupancy"              # Custom: wavefront occupancy

  # Granularity per dimension
  feature_bins:
    complexity: 12
    diversity: 10
    register_pressure: 10      # 10 levels of VGPR usage
    memory_efficiency: 12      # 12 levels of L2 hit rate
    occupancy: 8               # 8 levels of occupancy

  # Sampling behavior
  elite_selection_ratio: 0.3
  exploitation_ratio: 0.65     # Slightly favor exploration

  # Island management
  migration_interval: 30       # Migrate every 30 generations
  migration_rate: 0.12         # 12% migration

# Evaluator Configuration
evaluator:
  timeout: 180                 # 3 min per evaluation (rocprof is slow)
  parallel_evaluations: 1      # Sequential (GPU profiling)
  use_llm_feedback: false

# Evolution Strategy
diff_based_evolution: false    # Start with full rewrites for CUDA→HIP port
allow_full_rewrites: true
max_code_length: 25000         # HIP kernels can be verbose

# Paths (customize for your system)
paths:
  llama_cpp_root: "/home/user/llama.cpp"
  target_kernel_file: "ggml/src/ggml-hip/solve_tri.hip"
  build_dir: "build"
  test_executable: "bin/test-backend-ops"
  rocprof_path: "/opt/rocm/bin/rocprof"
```

---

## 🔄 Customization Workflow

### **Phase 1: Baseline (Iterations 1-50)**

**Goal:** Establish baseline, verify everything works

1. Use simple system message
2. Run 50 iterations
3. Check:
   - Does it compile? (fix paths if not)
   - Does it run? (fix correctness if not)
   - What's the baseline score?

### **Phase 2: Guided Exploration (Iterations 50-200)**

**Goal:** Teach Claude about gfx906

1. Analyze what Claude tries (check logs)
2. Update system message with:
   - Successful patterns ("Use float4 - it worked well")
   - Failed patterns ("Don't reduce threads - hurts occupancy")
3. Adjust metric weights based on what matters
4. Run 150 more iterations

### **Phase 3: Fine-tuning (Iterations 200-500)**

**Goal:** Optimize configuration

1. Analyze feature dimensions:
   - Are programs clustered? (need more granularity)
   - Are cells empty? (too fine-grained)
2. Adjust `feature_bins` accordingly
3. Tune temperature (higher if stuck)
4. Consider switching to diff-based if stable

### **Phase 4: Refinement (Iterations 500+)**

**Goal:** Squeeze out final improvements

1. Increase population size (more diversity)
2. Add more islands (parallel strategies)
3. Fine-tune metric weights
4. Let it run until convergence

---

## 🎯 Key Takeaways

### **Most Important Actors to Customize:**

1. **Evaluator** (100% must change for AMD)
   - File paths
   - Build commands
   - Profiler (rocprof)
   - Metrics (AMD-specific)

2. **Prompt System Message** (critical for success)
   - Encode gfx906 knowledge
   - Specify constraints
   - Guide optimization strategies

3. **Database Feature Dimensions** (for diversity)
   - Add AMD-specific features
   - Tune granularity
   - Balance exploration vs exploitation

### **Actors You Can Mostly Leave Alone:**

4. **Controller** - default settings work well
5. **Iteration Worker** - logic is solid
6. **LLM Ensemble** - just point to CLI bridge

### **Configuration Philosophy:**

```
Start Simple → Observe → Refine → Repeat

Bad: Over-configure everything upfront
Good: Start with basics, iterate based on results
```

### **Success Metrics:**

- ✅ Score improves over time
- ✅ Database fills with diverse programs
- ✅ Claude's mutations make sense (not random)
- ✅ System runs stably for 1000+ iterations

---

This guide gives you complete control over OpenEvolve for AMD gfx906 optimization. Focus on the Evaluator and System Message first - they have the biggest impact!
