# Build Tool

`build.cmd` 或 `build.ps1` 用于一键打包 Windows 便携版命令行程序。

## 前置条件

```powershell
pip install -r requirements.txt
pip install -r src/buildtool/requirements-build.txt
```

## 打包

```powershell
src\buildtool\build.cmd
```

产物输出到 `src/buildtool/out/mdtx.exe`。

额外会生成：

- `src/buildtool/out/config.template.yaml`
- `src/buildtool/work/`
- `src/buildtool/spec/`

## 运行

首次使用可先初始化默认配置：

```powershell
src\buildtool\out\mdtx.exe --init-config
```

默认配置位置：`~/.mdtx/config.yaml`
