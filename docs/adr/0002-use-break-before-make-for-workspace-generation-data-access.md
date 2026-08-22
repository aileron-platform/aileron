# Workspace generation 資料存取採用 break-before-make

Workspace generation rotation 不允許新舊 Runtime login 同時存取同一 Workspace schema，避免並行 generation 模糊資料所有權與連線終止責任。因此 rotation 採用 break-before-make：新 generation 啟用前先撤銷舊 generation 的 Runtime login 並終止其連線；若新 generation 建立失敗，Workspace 維持沒有有效 generation 的狀態直到 durable job 重試，而不恢復舊授權。
