# Darwin Board

![Darwin Board system](docs/assets/darwin-board-system.svg)

Darwin Board is a self-tuning RC filter with reconfigurable component paths.
Set a cutoff frequency and the controller finds a matching circuit, checks a
backup for each active component, and monitors the response. If a component
fails, it tries the prepared backups before starting a fresh search.

## Run the lab

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m darwin_board.visualizer_server
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) and select **Run autonomous
cycle**.

## Documentation

Read the [technical overview](docs/README.md) for the control loop, benchmark,
ESP32 build, testing commands, and full documentation index.
