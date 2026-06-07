# AGENTS.md

## Cursor Cloud specific instructions

### Product overview

RhobanProject fork of **V-REP 3.0.1** (32-bit Linux): robotics simulator + C++ Remote API clients for quadruped/pentapod control. There is no `package.json`, `requirements.txt`, or Docker setup.

### Required services (E2E Example flow)

| Service | Start command | Notes |
|---------|---------------|-------|
| V-REP simulator | `cd /workspace/Vrep_32 && ./vrep.sh /workspace/Scenes/simulationQuadrupede.ttt` | Must run from `Vrep_32/`; needs `DISPLAY` (X11). Dismiss startup dialogs (Update check, mouse hint). |
| Example Client | See build/run below | Connects to `127.0.0.1:4242` (configured in `Vrep_32/remoteApiConnections.txt`). |

Optional: **Greg** genetic optimizer (`Greg/`) requires **GAlib** (`libga`) and is not part of the default E2E path.

### System dependencies (VM image, not in repo)

The bundled V-REP binary is **ELF 32-bit**. On x86_64 Ubuntu:

1. `sudo dpkg --add-architecture i386`
2. Install i386 runtime: `libc6:i386`, X11/GL libs, `libsm6:i386`, `libice6:i386`, etc.
3. **libpng12** is not in modern Ubuntu repos; install from Linux Uprising PPA deb: `libpng12-0:i386` (see `http://ppa.launchpad.net/linuxuprising/libpng12/ubuntu/pool/main/libp/libpng/`).
4. Build tools: `cmake`, `g++-multilib`, `libstdc++-14-dev`, `lib32stdc++-13-dev`

Verify V-REP loads: `cd Vrep_32 && LD_LIBRARY_PATH=$PWD ldd libv_rep.so` (no "not found").

### Build Example Client (32-bit)

The prebuilt `remoteApi.so` is 32-bit; the client **must** be compiled with `-m32`:

```bash
mkdir -p Example/build && cd Example/build
cmake -DCMAKE_C_FLAGS="-m32" -DCMAKE_CXX_FLAGS="-m32" ..
make -j$(nproc)
```

### Run Example Client

**Simulation must be stopped** in V-REP before connecting (required for `simxSynchronous`). Then:

```bash
cd Example/build
LD_LIBRARY_PATH=/workspace/Vrep_32/programming/remoteApiSharedLib:$LD_LIBRARY_PATH \
  ./Client 127.0.0.1 4242
```

The client runs a 60s sinusoidal motor demo. Stop with Ctrl+C or wait for completion.

### Gotchas

- `./vrep.sh` sets `LD_LIBRARY_PATH` to `Vrep_32/` for bundled Qt/Lua libs; do not launch `vrep` directly without it.
- If `simxSynchronous` fails, stop simulation in V-REP (Simulation → Stop) and ensure no other client is connected.
- `Greg/` build needs GAlib installed separately; it is not vendored.
- No automated test suite or linter in this repo.
