# MAH Android

业务资源来自 MAH，Android 外壳来自同级的 `MAH-UIApp`，图片和索引来自同级的 `mah_res`。
`interface.json` 保留 `Adb` 声明，由 App 映射到 AndroidNative。`binding` 和 `show` 由外壳兼容。

在 `MAH-UIApp` 执行：

```powershell
python scripts/build_mah.py --abi all --version v1.0.1-android.1
```

需要 JDK 17+ 和 Android SDK；在外壳的 `local.properties` 设置 `sdk.dir`，或配置 Android SDK 环境变量。
默认构建调试 APK；`--release` 使用外壳现有签名设置。模拟器可选 `--abi x86_64`，手机可选 `--abi arm64-v8a`。
已有匹配的 MaaFramework 和 Python 运行库时可加 `--skip-runtime`。

固定配对为 MaaFramework `v5.14.2` / MaaAgentCoreAndroid `3.13.15-maafw5.14.2`。
升级时同步更新构建脚本与 App 的项目包兼容性检查。

生成物：

- `MAH/build/android/pi/`：APK 内置完整资源，包含初始素材与文件归属清单。
- `MAH/build/android/MAH-project-android-<version>.zip`：项目更新包，包含 interface、pipeline、Python 脚本和默认数据，不包含独立素材。
- `MAH-UIApp/app/build/outputs/apk/`：APK。

更新分三路：APK 从 `software_github`，项目包从 `project_github`，素材从 `resource_github`。
Android 打包时生成前两个地址，不改变桌面用的源 interface。
项目包文件名和 manifest 中的 version 必须与发布 tag 一致。
素材沿用现有 `mah_res-full-<tag>.zip`；旧 hotfix 缺少基准与删除清单，App 不使用它。
GitHub 下载必须有 SHA-256，校验失败不会安装。

MAH 的 `Android project package` 工作流在版本 tag 上附加项目 ZIP，也可手动构建 artifact。
外壳的 `MAH Android APK` 工作流可手动构建 APK artifact；对外发布应配置固定的发布签名，
使用 `--release` 构建并将 APK 附加到外壳仓库对应版本的 Release。

App 保留 `config/`、用户 `data/` 和进度；更新仅清理同一通道之前管理的文件。
安装期间禁止开始任务，失败或安装中断会恢复上一份资源。
更新 APK 不会自动覆盖已独立更新的项目与素材；设置里的资源修复会恢复 APK 内置资源并保留用户数据。

本次验收范围是构建、安装与配置页面，不启动游戏；完整执行周期由使用者另行验证。
