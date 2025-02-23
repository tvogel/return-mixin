# PyADS Control Loop Service

This project provides a control loop service using PyADS and a web API for monitoring and adjusting PID parameters. The service runs as a Windows service and includes a web interface for diagnostics and PID parameter adjustments.

## Project Structure

- `web_api.py`: Flask web application for monitoring diagnostics and adjusting PID parameters.
- `service.py`: Windows service implementation to run the control loop and web API.
- `return_mixin.py`: Contains the control loop logic and PID parameter handling.

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/pyads-trial.git
    cd pyads-trial
    ```

2. Install the required Python packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Install the Windows service:
    ```sh
    python service.py install
    ```

4. Start the Windows service:
    ```sh
    python service.py start
    ```

If you encounter problems with `pythonservice.exe` starting up, in particular when using a `.venv`, try:

```sh
mklink /D lib .venv\lib
```
(see https://github.com/mhammond/pywin32/issues/1987#issuecomment-2676463879)

## Usage

### Web Interface

Access the web interface at `http://localhost:5000` to view diagnostics and adjust PID parameters.

### Diagnostics

The diagnostics table displays the following information:
- `dt`: Time difference between control loop iterations.
- `actual_value`: Current value read from the PLC.
- `error`: Difference between the actual value and the set point.
- `I_error`: Integrated error over time.
- `D_error`: Derivative of the error.
- `P`, `I`, `D`: Proportional, Integral, and Derivative components of the control output.
- `control_output`: Combined control output.
- `new_control_value`: New control value to be written to the PLC.

### PID Parameters

Adjust the PID parameters (`Kp`, `Ki`, `Kd`) and the set point using the input fields and the "Update PID" button.

## Development

To run the application locally for development purposes:
1. Start the control loop:
    ```sh
    python web_api.py
    ```

2. Access the web interface at `http://localhost:5000`.

## Uninstallation

To uninstall the Windows service:
```sh
python service.py remove
```

## License

This project is licensed under the MIT License.