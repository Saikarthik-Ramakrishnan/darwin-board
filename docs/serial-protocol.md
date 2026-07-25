# ESP32 serial protocol

Darwin Board uses a line-oriented ASCII protocol at 115200 baud. Every command
and response ends with a newline.

## Identity

```text
> ID?
< ID DARWIN_ESP32_1 FW=0.3.0
```

## Configure the switch fabric

Resistor indices are zero-based. The capacitor mask uses the lowest six bits.

```text
> SET R=2 C=0x15
< OK
```

## Measure a transient

```text
> STEP?
< STEP TAU_US=131.420 FC_HZ=1211.03 FIT_R2=0.99721
```

## Request a model-derived sweep

The firmware reconstructs a first-order frequency response from the measured
time constant.

```text
> SWEEP 100 10000 4
< SWEEP_DB -0.0296,-0.6091,-6.1084,-18.4052
```

## Read status

```text
> STATUS?
< STATUS MODE=STEP_MODEL TEMP_C=31.5 FC_HZ=1211.03 FIT_R2=0.99721 R=2 C=0x15
```

## Errors

Errors begin with `ERR`:

```text
ERR INVALID_CONFIGURATION
ERR INVALID_SWEEP
ERR TRANSIENT_FIT_FAILED
ERR UNKNOWN_COMMAND
```

The host treats any error response, timeout, malformed number, or unexpected
point count as a failed measurement.
