package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

type WorkspaceManagerToken struct {
	UserID    string `json:"user_id"`
	CreatedAt int64  `json:"created_at"`
	ExpiresAt int64  `json:"expires_at"`
}

func main() {
	// 連接 Redis
	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
		DB:   0,
	})

	ctx := context.Background()

	// 測試 token
	tokenKey := "acc_9fca6442-5867-48c1-92c6-80d44b15cae4"
	redisKey := fmt.Sprintf("auth:access_token:%s", tokenKey)

	fmt.Println("=== Token 驗證測試 ===")
	fmt.Println()

	// 1. 從 Redis 讀取 token
	fmt.Println("1. 從 Redis 讀取 token")
	tokenData, err := redisClient.Get(ctx, redisKey).Result()
	if err != nil {
		fmt.Printf("   ❌ 錯誤: %v\n", err)
		return
	}
	fmt.Printf("   ✅ Token 資料: %s\n", tokenData)
	fmt.Println()

	// 2. 解析 JSON
	fmt.Println("2. 解析 JSON")
	var wmToken WorkspaceManagerToken
	if err := json.Unmarshal([]byte(tokenData), &wmToken); err != nil {
		fmt.Printf("   ❌ JSON 解析失敗: %v\n", err)
		return
	}
	fmt.Printf("   ✅ 解析成功\n")
	fmt.Printf("   - user_id: %s\n", wmToken.UserID)
	fmt.Printf("   - created_at: %d (類型: int64)\n", wmToken.CreatedAt)
	fmt.Printf("   - expires_at: %d (類型: int64)\n", wmToken.ExpiresAt)
	fmt.Println()

	// 3. 驗證時間戳
	fmt.Println("3. 驗證時間戳")
	currentTime := time.Now().Unix()
	fmt.Printf("   - 當前時間戳: %d\n", currentTime)
	fmt.Printf("   - Token 創建時間: %d\n", wmToken.CreatedAt)
	fmt.Printf("   - Token 過期時間: %d\n", wmToken.ExpiresAt)
	fmt.Printf("   - 有效期: %d 秒 (%.1f 小時)\n",
		wmToken.ExpiresAt-wmToken.CreatedAt,
		float64(wmToken.ExpiresAt-wmToken.CreatedAt)/3600)
	fmt.Printf("   - 剩餘時間: %d 秒 (%.1f 分鐘)\n",
		wmToken.ExpiresAt-currentTime,
		float64(wmToken.ExpiresAt-currentTime)/60)
	fmt.Println()

	// 4. 驗證 token 是否過期
	fmt.Println("4. 驗證 token 是否過期")
	if currentTime >= wmToken.ExpiresAt {
		fmt.Printf("   ❌ Token 已過期\n")
	} else {
		fmt.Printf("   ✅ Token 有效\n")
	}
	fmt.Println()

	// 5. 測試時間轉換
	fmt.Println("5. 時間轉換測試")
	createdTime := time.Unix(wmToken.CreatedAt, 0)
	expiresTime := time.Unix(wmToken.ExpiresAt, 0)
	fmt.Printf("   - 創建時間: %s\n", createdTime.Format("2006-01-02 15:04:05"))
	fmt.Printf("   - 過期時間: %s\n", expiresTime.Format("2006-01-02 15:04:05"))
	fmt.Println()

	fmt.Println("=== 測試完成 ===")
}
