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
APK 与项目包统一发布在 MAH 的 Release，因此前两个地址都指向 MAH；素材仍指向 mah_res。
Android 打包时生成这些地址，不改变桌面用的源 interface。
项目包文件名和 manifest 中的 version 必须与发布 tag 一致。
素材沿用现有 `mah_res-full-<tag>.zip`；旧 hotfix 缺少基准与删除清单，App 不使用它。
GitHub 下载必须有 SHA-256，校验失败不会安装。

向 MAH 的 `main` 分支推送后，`Android APK` 工作流会自动拉取 `MAH-UIApp/main` 和
`mah_res/main`，读取本仓库的配方，编译包含 ARM64 和 x86_64 的通用调试 APK。
在该次运行的 Artifacts 中下载 `MAH-Android-APK`。连续推送会取消同一分支尚未完成的旧构建。
也可在 MAH 的 Actions 页面手动运行 `Android APK`，选择 App、素材的分支或标签并指定版本号；
版本号留空时自动使用 MAH 的 Git 版本加上本次 CI 运行编号。
修改 App 外壳后，需先把对应改动推送到 MAH-UIApp，供 MAH 的构建读取。

推送 `v*` 版本标签时，由 MAH 原有的 `install` 工作流调用同一套 APK 构建，版本号使用
本次推送的标签。等待桌面包、APK、项目更新 ZIP 全部完成后，由 `install/release` 统一发布。
Release 中的 Android 文件为 `MAH-android-universal-<tag>-debug.apk` 和
`MAH-project-android-<tag>.zip`，不再生成旧的 Android 平台 ZIP 和 Android 增量 ZIP。
`Android project package` 仅保留手动生成项目包 artifact，不再单独创建 Release。
外壳仓库原有的 `MAH Android APK` 手动入口仍可使用。
目前 APK 仍为调试构建；正式发行需要配置固定签名并切换到 `--release`。

工作流修改必须先提交并推送；版本标签也必须包含这些提交。重跑旧标签的旧运行不会使用
尚未提交的文件或之后才修改的工作流。

App 保留 `config/`、用户 `data/` 和进度；更新仅清理同一通道之前管理的文件。
安装期间禁止开始任务，失败或安装中断会恢复上一份资源。
更新 APK 不会自动覆盖已独立更新的项目与素材；设置里的资源修复会恢复 APK 内置资源并保留用户数据。

本次验收范围是构建、安装与配置页面，不启动游戏；完整执行周期由使用者另行验证。
