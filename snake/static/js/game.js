document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('game-canvas');
    const ctx = canvas.getContext('2d');
    const currentScoreElement = document.getElementById('current-score');
    const highScoreElement = document.getElementById('high-score');
    
    const gridSize = 20;
    const tileCount = canvas.width / gridSize;
    
    let snake = [{x: 10, y: 10}];
    let food = {x: 5, y: 5};
    let direction = {x: 0, y: 0};
    let lastDirection = {x: 0, y: 0};
    let gameSpeed = 150;
    let score = 0;
    let highScore = localStorage.getItem('highScore') || 0;
    let gameRunning = false;
    let gameLoop;
    
    highScoreElement.textContent = highScore;
    
    function drawGame() {
        // Очистка холста
        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Рисуем змейку
        ctx.fillStyle = '#4CAF50';
        snake.forEach(segment => {
            ctx.fillRect(segment.x * gridSize, segment.y * gridSize, gridSize - 2, gridSize - 2);
        });
        
        // Рисуем еду
        ctx.fillStyle = '#f44336';
        ctx.fillRect(food.x * gridSize, food.y * gridSize, gridSize - 2, gridSize - 2);
    }
    
    function moveSnake() {
        const head = {x: snake[0].x + direction.x, y: snake[0].y + direction.y};
        
        // Проверка на столкновение с границами
        if (head.x < 0 || head.x >= tileCount || head.y < 0 || head.y >= tileCount) {
            gameOver();
            return;
        }
        
        // Проверка на столкновение с собой
        for (let i = 1; i < snake.length; i++) {
            if (head.x === snake[i].x && head.y === snake[i].y) {
                gameOver();
                return;
            }
        }
        
        // Добавляем новую голову
        snake.unshift(head);
        
        // Проверка на съедение еды
        if (head.x === food.x && head.y === food.y) {
            score += 10;
            currentScoreElement.textContent = score;
            placeFood();
            
            // Увеличиваем скорость каждые 50 очков
            if (score % 50 === 0 && gameSpeed > 50) {
                gameSpeed -= 10;
                clearInterval(gameLoop);
                gameLoop = setInterval(game, gameSpeed);
            }
        } else {
            // Удаляем хвост, если не съели еду
            snake.pop();
        }
    }
    
    function placeFood() {
        let foodPosition;
        do {
            foodPosition = {
                x: Math.floor(Math.random() * tileCount),
                y: Math.floor(Math.random() * tileCount)
            };
        } while (snake.some(segment => segment.x === foodPosition.x && segment.y === foodPosition.y));
        
        food = foodPosition;
    }
    
    function game() {
        moveSnake();
        drawGame();
    }
    
    function gameOver() {
        clearInterval(gameLoop);
        gameRunning = false;
        
        // Обновляем рекорд
        if (score > highScore) {
            highScore = score;
            localStorage.setItem('highScore', highScore);
            highScoreElement.textContent = highScore;
        }
        
        // Отправляем результат на сервер, если пользователь авторизован
        if (score > 0) {
            fetch('/save_score', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ score: score })
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        console.error('Error saving score:', err.message);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    console.log('Score saved successfully');
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
        
        alert(`Игра окончена! Ваш счет: ${score}`);
        resetGame();
    }
    
    function resetGame() {
        snake = [{x: 10, y: 10}];
        direction = {x: 0, y: 0};
        lastDirection = {x: 0, y: 0};
        score = 0;
        currentScoreElement.textContent = score;
        placeFood();
    }
    
    function startGame() {
        if (!gameRunning) {
            resetGame();
            gameRunning = true;
            gameLoop = setInterval(game, gameSpeed);
        }
    }
    
    // Управление
    document.addEventListener('keydown', e => {
        // Начинаем игру при первом нажатии
        if (!gameRunning && (e.key.startsWith('Arrow') || ['w', 'a', 's', 'd'].includes(e.key.toLowerCase()))) {
            startGame();
        }
        
        // Изменяем направление
        switch(e.key) {
            case 'ArrowUp':
            case 'w':
                if (lastDirection.y === 0) {
                    direction = {x: 0, y: -1};
                    lastDirection = direction;
                }
                break;
            case 'ArrowDown':
            case 's':
                if (lastDirection.y === 0) {
                    direction = {x: 0, y: 1};
                    lastDirection = direction;
                }
                break;
            case 'ArrowLeft':
            case 'a':
                if (lastDirection.x === 0) {
                    direction = {x: -1, y: 0};
                    lastDirection = direction;
                }
                break;
            case 'ArrowRight':
            case 'd':
                if (lastDirection.x === 0) {
                    direction = {x: 1, y: 0};
                    lastDirection = direction;
                }
                break;
        }
    });
    
    // Начальное положение еды
    placeFood();
    drawGame();
    
    // Кнопка для мобильных устройств
    const startButton = document.createElement('button');
    startButton.textContent = 'Начать игру';
    startButton.className = 'btn';
    startButton.style.marginTop = '20px';
    startButton.addEventListener('click', startGame);
    document.querySelector('.game-container').appendChild(startButton);
});