# Testes no PC (sem rede e sem PlatformIO) e servidor de PC para a suíte de conformidade.
CXX ?= g++
CXXFLAGS ?= -std=c++17 -O1 -Wall -Wextra -Wpedantic
LIB := lib/elm327
BUILD := build
LIB_SRC := $(wildcard $(LIB)/*.cpp)
TEST_SRC := $(wildcard test/*.cpp)
GOLDEN := $(abspath ../tests/conformance/dourado.json)

.PHONY: test host_server clean

test: $(BUILD)/run_tests
	$(BUILD)/run_tests

host_server: $(BUILD)/host_server

$(BUILD)/run_tests: $(LIB_SRC) $(TEST_SRC) $(wildcard $(LIB)/*.hpp test/*.hpp) $(GOLDEN)
	@mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(LIB) -Itest -DGOLDEN_PATH='"$(GOLDEN)"' $(LIB_SRC) $(TEST_SRC) -o $@

$(BUILD)/host_server: $(LIB_SRC) tools/host_server.cpp $(wildcard $(LIB)/*.hpp)
	@mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) -I$(LIB) $(LIB_SRC) tools/host_server.cpp -o $@ -pthread

clean:
	rm -rf $(BUILD)
