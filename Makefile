#================DO NOT MODIFY BELOW===================== Compiler and simulator settings
IVERILOG = iverilog
VVP = vvp
COCOTB_LIBS = $(shell cocotb-config --lib-dir)
COCOTB_VPI_MODULE = $(shell cocotb-config --lib-name vpi icarus)
COCOTB_LIBPYTHON = $(shell cocotb-config --libpython)
COCOTB_PYTHON_BIN = $(shell cocotb-config --python-bin)

SIM_BUILD_DIR = sim_build
SIM_VVP = $(SIM_BUILD_DIR)/sim.vvp
COCOTB_RUN = rm -f results.xml && PYTHONOPTIMIZE=$(NOASSERT) MODULE=$(1) COCOTB_TEST_MODULES=$(1) LIBPYTHON_LOC=$(COCOTB_LIBPYTHON) PYGPI_PYTHON_BIN=$(COCOTB_PYTHON_BIN) $(VVP) -M $(COCOTB_LIBS) -m $(COCOTB_VPI_MODULE) $(SIM_VVP)
CHECK_RESULTS = python -c "import sys, xml.etree.ElementTree as ET; root=ET.parse('results.xml').getroot(); sys.exit(1 if root.findall('.//failure') or root.findall('.//error') else 0)"

# Force bash shell on Windows so ! negation and Unix commands work
ifeq ($(OS),Windows_NT)
  SHELL = C:/Program Files/Git/bin/sh.exe
  .SHELLFLAGS = -c
endif

# Environment variables
export COCOTB_REDUCED_LOG_FMT=1
ifeq ($(OS),Windows_NT)
  export PYTHONPATH := $(abspath test);$(PYTHONPATH)
else
  export PYTHONPATH := $(abspath test):$(PYTHONPATH)
endif

#=============== MODIFY BELOW ======================
# ********** IF YOU HAVE A NEW VERILOG FILE, ADD IT TO THE SOURCES VARIABLE
SOURCES = src/pe.sv \
          src/leaky_relu_child.sv \
          src/leaky_relu_parent.sv \
          src/leaky_relu_derivative_child.sv \
          src/leaky_relu_derivative_parent.sv \
          src/systolic.sv \
          src/bias_child.sv \
          src/bias_parent.sv \
          src/fixedpoint.sv \
          src/control_unit.sv \
          src/unified_buffer.sv \
          src/vpu.sv \
          src/loss_parent.sv \
		  src/loss_child.sv \
		  src/tpu.sv \
		  src/gradient_descent.sv

LINT_SOURCES = $(filter-out src/fixedpoint.sv,$(SOURCES))
VERIBLE_RULES = -always-comb,-always-ff-non-blocking,-line-length,-unpacked-dimensions-range-ordering,-generate-label-prefix

# MODIFY 1) variable next to -s 
# MODIFY 2) variable next to $(SOURCES)
# MODIFY 3) variable right of MODULE=
# MODIFY 4) file name next to mv (i.e. pe.vcd)


# Test targets
test_pe: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s pe -s dump -g2012 $(SOURCES) test/dump_pe.sv
	$(call COCOTB_RUN,test_pe)
	$(CHECK_RESULTS)
	mv pe.vcd waveforms/ 2>/dev/null || true

test_systolic: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s systolic -s dump -g2012 $(SOURCES) test/dump_systolic.sv
	$(call COCOTB_RUN,test_systolic)
	$(CHECK_RESULTS)
	mv systolic.vcd waveforms/ 2>/dev/null || true

test_unified_buffer: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s unified_buffer -s dump -g2012 $(SOURCES) test/dump_unified_buffer.sv
	$(call COCOTB_RUN,test_unified_buffer)
	$(CHECK_RESULTS)
	mv unified_buffer.vcd waveforms/ 2>/dev/null || true

# Aggregate: every self-checking benchmark target of the baseline
TESTS = pe systolic unified_buffer loss_parent leaky_relu_parent \
        leaky_relu_derivative_parent bias_parent vpu tpu gradient_descent

.PHONY: test $(addprefix test_,$(TESTS))
test: $(addprefix test_,$(TESTS))

# Loss module test

test_loss_parent: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s loss_parent -s dump -g2012 $(SOURCES) test/dump_loss_parent.sv
	$(call COCOTB_RUN,test_loss_parent)
	$(CHECK_RESULTS)
	mv loss_parent.vcd waveforms/ 2>/dev/null || true

# Leaky ReLU module tests
test_leaky_relu_parent: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s leaky_relu_parent -s dump -g2012 $(SOURCES) test/dump_leaky_relu_parent.sv
	$(call COCOTB_RUN,test_leaky_relu_parent)
	$(CHECK_RESULTS)
	mv leaky_relu_parent.vcd waveforms/ 2>/dev/null || true

test_leaky_relu_derivative_parent: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s leaky_relu_derivative_parent -s dump -g2012 $(SOURCES) test/dump_leaky_relu_derivative_parent.sv
	$(call COCOTB_RUN,test_leaky_relu_derivative_parent)
	$(CHECK_RESULTS)
	mv leaky_relu_derivative_parent.vcd waveforms/ 2>/dev/null || true

# Bias module tests
test_bias_parent: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s bias_parent -s dump -g2012 $(SOURCES) test/dump_bias_parent.sv
	$(call COCOTB_RUN,test_bias_parent)
	$(CHECK_RESULTS)
	mv bias_parent.vcd waveforms/ 2>/dev/null || true

# Vector Processing unit test
test_vpu: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s vpu -s dump -g2012 $(SOURCES) test/dump_vpu.sv
	$(call COCOTB_RUN,test_vpu)
	$(CHECK_RESULTS)
	mv vpu.vcd waveforms/ 2>/dev/null || true

test_tpu: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s tpu -s dump -g2012 $(SOURCES) test/dump_tpu.sv
	$(call COCOTB_RUN,test_tpu)
	$(CHECK_RESULTS)
	mv tpu.vcd waveforms/ 2>/dev/null || true

test_gradient_descent: $(SIM_BUILD_DIR)
	$(IVERILOG) -o $(SIM_VVP) -s gradient_descent -s dump -g2012 $(SOURCES) test/dump_gradient_descent.sv
	$(call COCOTB_RUN,test_gradient_descent)
	$(CHECK_RESULTS)
	mv gradient_descent.vcd waveforms/ 2>/dev/null || true


# ============ DO NOT MODIFY BELOW THIS LINE ==============

# Create simulation build directory and waveforms directory
$(SIM_BUILD_DIR):
	mkdir -p $(SIM_BUILD_DIR)
	mkdir -p waveforms

# Waveform viewing
show_%: waveforms/%.vcd waveforms/%.gtkw
	gtkwave $^

# Linting
lint:
	verible-verilog-lint $(LINT_SOURCES) --rules_config verible.rules --rules "$(VERIBLE_RULES)"

# Cleanup
clean:
	rm -rf waveforms/*vcd $(SIM_BUILD_DIR) test/__pycache__

.PHONY: clean lint
