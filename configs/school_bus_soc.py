"""Smart School Bus SoC Configuration for gem5 (SE mode).

Supports both x86 (e.g. build/X86/gem5.opt) and RISC-V (e.g. build/RISCV/gem5.opt).
Automatically configures the appropriate CPU models, L1/L2 caches, DDR3 memory,
and interrupt controllers based on the available gem5 ISA build.

Usage examples:
  # With x86 gem5 build:
  build/X86/gem5.opt configs/school_bus_soc.py --binary build/school_bus_soc --args "40 2024 1"

  # With RISC-V gem5 build:
  build/RISCV/gem5.opt configs/school_bus_soc.py --binary build/school_bus_soc.riscv --args "40 2024 1"
"""

import argparse
import os
import sys

import m5
from m5.objects import *


def parse_arguments():
    here = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(here, ".."))

    # Auto-detect default binary
    default_bin = os.path.join(root_dir, "build", "school_bus_soc")
    if not os.path.isfile(default_bin):
        for candidate in ("school_bus_soc.x86", "school_bus_soc.riscv", "school_bus_soc"):
            p = os.path.join(root_dir, "build", candidate)
            if os.path.isfile(p):
                default_bin = p
                break

    p = argparse.ArgumentParser(description="Smart School Bus SoC (gem5 SE mode)")
    p.add_argument("--binary", default=default_bin, help="Static executable to simulate")
    p.add_argument("--args", default="40 2024 1", help="Arguments passed to the executable")
    p.add_argument("--cpu-type", default="timing", choices=["timing", "minor", "o3"])
    p.add_argument("--clock", default="1GHz", help="Processor clock frequency")
    p.add_argument("--l1i-size", default="32KiB", help="L1 Instruction cache size")
    p.add_argument("--l1d-size", default="32KiB", help="L1 Data cache size")
    p.add_argument("--l2-size", default="256KiB", help="Shared L2 cache size")
    p.add_argument("--mem-size", default="512MiB", help="Main memory size")
    return p.parse_args()


class L1Cache(Cache):
    assoc = 4
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20

    def connectCPU(self, cpu):
        raise NotImplementedError

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L1ICache(L1Cache):
    size = "32KiB"

    def connectCPU(self, cpu):
        self.cpu_side = cpu.icache_port


class L1DCache(L1Cache):
    size = "32KiB"

    def connectCPU(self, cpu):
        self.cpu_side = cpu.dcache_port


class L2Cache(Cache):
    size = "256KiB"
    assoc = 8
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 20
    tgts_per_mshr = 12

    def connectCPUSideBus(self, bus):
        self.cpu_side = bus.mem_side_ports

    def connectMemSideBus(self, bus):
        self.mem_side = bus.cpu_side_ports


def resolve_cpu_class(cpu_type):
    """Detects available CPU classes in the current gem5 ISA build."""
    if hasattr(m5.objects, "X86TimingSimpleCPU"):
        # x86 ISA build
        arch = "X86"
        classes = {
            "timing": m5.objects.X86TimingSimpleCPU,
            "minor": getattr(m5.objects, "X86MinorCPU", getattr(m5.objects, "MinorCPU", m5.objects.X86TimingSimpleCPU)),
            "o3": getattr(m5.objects, "X86O3CPU", getattr(m5.objects, "DerivO3CPU", getattr(m5.objects, "O3CPU", m5.objects.X86TimingSimpleCPU))),
        }
    elif hasattr(m5.objects, "RiscvTimingSimpleCPU"):
        # RISC-V ISA build
        arch = "RISCV"
        classes = {
            "timing": m5.objects.RiscvTimingSimpleCPU,
            "minor": getattr(m5.objects, "RiscvMinorCPU", getattr(m5.objects, "MinorCPU", m5.objects.RiscvTimingSimpleCPU)),
            "o3": getattr(m5.objects, "RiscvO3CPU", getattr(m5.objects, "DerivO3CPU", getattr(m5.objects, "O3CPU", m5.objects.RiscvTimingSimpleCPU))),
        }
    else:
        # Generic fallback
        arch = "Generic"
        classes = {
            "timing": getattr(m5.objects, "TimingSimpleCPU"),
            "minor": getattr(m5.objects, "MinorCPU", getattr(m5.objects, "TimingSimpleCPU")),
            "o3": getattr(m5.objects, "DerivO3CPU", getattr(m5.objects, "O3CPU", getattr(m5.objects, "TimingSimpleCPU"))),
        }
    return arch, classes.get(cpu_type, classes["timing"])


def build_system(args):
    binary = os.path.abspath(args.binary)
    if not os.path.isfile(binary):
        print("ERROR: executable binary not found: %s" % binary)
        print("Please compile the application first (e.g., using `make` or the experiment runner).")
        sys.exit(1)

    arch, cpu_cls = resolve_cpu_class(args.cpu_type)

    system = System()
    system.clk_domain = SrcClockDomain(clock=args.clock, voltage_domain=VoltageDomain())
    system.mem_mode = "timing"
    system.mem_ranges = [AddrRange(args.mem_size)]
    system.cache_line_size = 64

    # CPU instantiate
    system.cpu = cpu_cls()

    # L1 Caches
    system.cpu.icache = L1ICache(size=args.l1i_size)
    system.cpu.dcache = L1DCache(size=args.l1d_size)
    system.cpu.icache.connectCPU(system.cpu)
    system.cpu.dcache.connectCPU(system.cpu)

    # L2 Bus & Shared L2 Cache
    system.l2bus = L2XBar()
    system.cpu.icache.connectBus(system.l2bus)
    system.cpu.dcache.connectBus(system.l2bus)

    system.l2cache = L2Cache(size=args.l2_size)
    system.l2cache.connectCPUSideBus(system.l2bus)

    # System Memory Bus
    system.membus = SystemXBar()
    system.l2cache.connectMemSideBus(system.membus)

    # Interrupt Controller
    system.cpu.createInterruptController()
    if hasattr(system.cpu, "interrupts"):
        for intr in system.cpu.interrupts:
            if hasattr(intr, "pio"):
                intr.pio = system.membus.mem_side_ports
            if hasattr(intr, "int_requestor"):
                intr.int_requestor = system.membus.cpu_side_ports
            if hasattr(intr, "int_responder"):
                intr.int_responder = system.membus.mem_side_ports

    # DDR3 Memory Controller
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports

    system.system_port = system.membus.cpu_side_ports

    # System-call emulation workload
    system.workload = SEWorkload.init_compatible(binary)
    process = Process()
    process.executable = binary
    process.cmd = [binary] + args.args.split()
    system.cpu.workload = process
    system.cpu.createThreads()

    return system, binary, arch


def main():
    args = parse_arguments()
    system, binary, arch = build_system(args)

    root = Root(full_system=False, system=system)

    print("=" * 66)
    print(" Smart School Bus Safety and Priority Management SoC Simulation")
    print(" Architecture : %s" % arch)
    print(" CPU Model    : %s (%s)" % (args.cpu_type, system.cpu.__class__.__name__))
    print(" Clock        : %s" % args.clock)
    print(" Memory       : %s (DDR3_1600_8x8)" % args.mem_size)
    print(" Caches       : L1I=%s, L1D=%s, L2=%s" % (args.l1i_size, args.l1d_size, args.l2_size))
    print(" Binary       : %s" % binary)
    print(" Arguments    : %s" % args.args)
    print("=" * 66)

    m5.instantiate()
    print("Starting gem5 simulation...")
    exit_event = m5.simulate()
    print("Exiting @ tick %d because %s" % (m5.curTick(), exit_event.getCause()))

    code = exit_event.getCode()
    if code != 0:
        sys.exit(code)


if __name__ == "__m5_main__":
    main()
elif __name__ == "__main__":
    main()
