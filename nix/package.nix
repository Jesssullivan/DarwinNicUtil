{
  lib,
  stdenv,
  python3Packages,
}:

python3Packages.buildPythonApplication rec {
  pname = "darwin-nic";
  version = "2.1.2";
  pyproject = true;

  src = lib.cleanSource ./..;

  build-system = with python3Packages; [
    hatchling
  ];

  dependencies = with python3Packages; [
    rich
    typing-extensions
  ];

  nativeCheckInputs = with python3Packages; [
    pytestCheckHook
    pytest-mock
  ];

  disabledTests =
    # These tests patch builtins.input but the code uses Rich Confirm.ask(),
    # causing hangs in non-interactive builds
    [
      "test_confirm_configuration_user_accepts"
      "test_confirm_configuration_user_rejects"
      "test_confirm_configuration_invalid_input"
      "test_configure_success"
      "test_configure_failure"
    ]
    # macOS-specific tests that mock ifconfig/networksetup
    ++ lib.optionals (!stdenv.hostPlatform.isDarwin) [
      "test_detect_usb_nic"
      "test_detect_no_usb_nic"
      "test_configure_interface"
      "test_macos"
    ];

  pythonImportsCheck = [
    "darwin_mgmt_nic"
  ];

  meta = {
    description = "USB network interface configurator for management access to network devices";
    homepage = "https://github.com/Jesssullivan/DarwinNicUtil";
    license = lib.licenses.zlib;
    maintainers = [ ];
    mainProgram = "darwin-nic";
    platforms = lib.platforms.unix;
  };
}
