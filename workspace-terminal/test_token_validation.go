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
	// Connect to Redis
	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
		DB:   0,
	})

	ctx := context.Background()

	// Test token
	tokenKey := "acc_9fca6442-5867-48c1-92c6-80d44b15cae4"
	redisKey := fmt.Sprintf("auth:access_token:%s", tokenKey)

	fmt.Println("=== Token Validation Test ===")
	fmt.Println()

	// 1. Read token from Redis
	fmt.Println("1. Read token from Redis")
	tokenData, err := redisClient.Get(ctx, redisKey).Result()
	if err != nil {
		fmt.Printf("   ❌ Error: %v\n", err)
		return
	}
	fmt.Printf("   ✅ Token data: %s\n", tokenData)
	fmt.Println()

	// 2. Parse JSON
	fmt.Println("2. Parse JSON")
	var wmToken WorkspaceManagerToken
	if err := json.Unmarshal([]byte(tokenData), &wmToken); err != nil {
		fmt.Printf("   ❌ JSON parse failed: %v\n", err)
		return
	}
	fmt.Printf("   ✅ Parse successful\n")
	fmt.Printf("   - user_id: %s\n", wmToken.UserID)
	fmt.Printf("   - created_at: %d (type: int64)\n", wmToken.CreatedAt)
	fmt.Printf("   - expires_at: %d (type: int64)\n", wmToken.ExpiresAt)
	fmt.Println()

	// 3. Verify timestamps
	fmt.Println("3. Verify timestamps")
	currentTime := time.Now().Unix()
	fmt.Printf("   - Current timestamp: %d\n", currentTime)
	fmt.Printf("   - Token created at: %d\n", wmToken.CreatedAt)
	fmt.Printf("   - Token expires at: %d\n", wmToken.ExpiresAt)
	fmt.Printf("   - Validity period: %d seconds (%.1f hours)\n",
		wmToken.ExpiresAt-wmToken.CreatedAt,
		float64(wmToken.ExpiresAt-wmToken.CreatedAt)/3600)
	fmt.Printf("   - Remaining time: %d seconds (%.1f minutes)\n",
		wmToken.ExpiresAt-currentTime,
		float64(wmToken.ExpiresAt-currentTime)/60)
	fmt.Println()

	// 4. Check if token is expired
	fmt.Println("4. Check if token is expired")
	if currentTime >= wmToken.ExpiresAt {
		fmt.Printf("   ❌ Token expired\n")
	} else {
		fmt.Printf("   ✅ Token valid\n")
	}
	fmt.Println()

	// 5. Test time conversion
	fmt.Println("5. Test time conversion")
	createdTime := time.Unix(wmToken.CreatedAt, 0)
	expiresTime := time.Unix(wmToken.ExpiresAt, 0)
	fmt.Printf("   - Created at: %s\n", createdTime.Format("2006-01-02 15:04:05"))
	fmt.Printf("   - Expires at: %s\n", expiresTime.Format("2006-01-02 15:04:05"))
	fmt.Println()

	fmt.Println("=== Test Complete ===")
}
