// Глобальные переменные
let taskId = null;
let score = 0;
let maxScore = 0;
let num1 = 0;
let num2 = 0;
let correctAnswer = 0;
let ws = null;
let isPaused = false;
let isBreak = false;

// Загрузка информации о задании
async function loadTaskInfo() {
    try {
        const response = await fetch(`/task/${taskId}/info`, {
            credentials: 'include'
        });
        if (response.ok) {
            const taskInfo = await response.json();
            maxScore = taskInfo.max_score;
            document.getElementById('taskName').textContent = taskInfo.name;
            document.getElementById('subjectName').textContent = taskInfo.subjects_name;
            updateScore();
        }
    } catch (error) {
        console.error('Ошибка при загрузке информации о задании:', error);
    }
}

// Инициализация WebSocket соединения
function initWebSocket() {
    ws = new WebSocket(`ws://${window.location.host}/ws/task/${taskId}`);

    ws.onmessage = function (event) {
        const data = JSON.parse(event.data);

        if (data.type === "time_update") {
            updateTimeDisplay(data.elapsed_time);
            updateProgressBar(data.elapsed_time, data.max_time);
            isPaused = data.is_paused;
            isBreak = data.is_break;
            score = data.score;
            maxScore = data.max_score;
            updateScore();
            updateUIState();
        } else if (data.type === "break") {
            showBreakMessage();
        }
    };

    ws.onclose = function () {
        console.log("WebSocket соединение закрыто");
    };
}

// Генерация нового задания
function generateTask() {
    num1 = Math.floor(Math.random() * 20) + 1;
    num2 = Math.floor(Math.random() * 20) + 1;
    correctAnswer = num1 + num2;

    document.getElementById('num1').textContent = num1;
    document.getElementById('num2').textContent = num2;
    document.getElementById('answer').value = '';
}

// Проверка ответа
async function checkAnswer() {
    const userAnswer = parseInt(document.getElementById('answer').value);

    if (isNaN(userAnswer)) {
        alert('Пожалуйста, введите число');
        return;
    }

    if (userAnswer === correctAnswer) {
        try {
            const response = await fetch(`/check_answer/${taskId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ answer: userAnswer }),
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                score = data.score;
                updateScore();

                if (score >= maxScore) {
                    await finishTask();
                } else {
                    generateTask();
                }
            } else {
                const errorData = await response.json();
                alert(errorData.detail || 'Ошибка при проверке ответа');
            }
        } catch (error) {
            console.error('Ошибка при проверке ответа:', error);
            alert('Ошибка при проверке ответа');
        }
    } else {
        alert('Неверный ответ. Попробуйте еще раз!');
    }

    document.getElementById('answer').value = '';
}

// Обновление отображения счета
function updateScore() {
    document.getElementById('score').textContent = `${score}/${maxScore}`;
}

// Обновление отображения времени
function updateTimeDisplay(elapsedSeconds) {
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = Math.floor(elapsedSeconds % 60);
    document.getElementById('timeDisplay').textContent =
        `${minutes} мин ${seconds} сек`;
}

// Обновление прогресс-бара
function updateProgressBar(elapsed, max) {
    const percentage = (elapsed / max) * 100;
    document.getElementById('progressBar').style.width = `${percentage}%`;
}

// Показать сообщение о перерыве
function showBreakMessage() {
    document.getElementById('breakMessage').style.display = 'block';
    document.getElementById('taskContent').style.display = 'none';
    isBreak = true;
    updateUIState();
}

// Обновление состояния UI
function updateUIState() {
    const taskContent = document.getElementById('taskContent');
    const pauseButton = document.getElementById('pauseButton');
    const resumeButton = document.getElementById('resumeButton');
    const answerInput = document.getElementById('answer');
    const checkButton = document.getElementById('checkButton');

    if (isPaused || isBreak) {
        taskContent.style.display = 'none';
        pauseButton.disabled = true;
        resumeButton.disabled = isBreak;
        answerInput.disabled = true;
        checkButton.disabled = true;
    } else {
        taskContent.style.display = 'block';
        pauseButton.disabled = false;
        resumeButton.disabled = true;
        answerInput.disabled = false;
        checkButton.disabled = false;
    }
}

// Пауза задания
async function pauseTask() {
    try {
        const response = await fetch(`/pause_task/${taskId}`, {
            method: 'POST',
            credentials: 'include'
        });
        if (response.ok) {
            isPaused = true;
            updateUIState();
        }
    } catch (error) {
        console.error('Ошибка при постановке на паузу:', error);
    }
}

// Возобновление задания
async function resumeTask() {
    try {
        const response = await fetch(`/resume_task/${taskId}`, {
            method: 'POST',
            credentials: 'include'
        });
        if (response.ok) {
            isPaused = false;
            updateUIState();
        }
    } catch (error) {
        console.error('Ошибка при возобновлении:', error);
    }
}

// Завершение задания
async function finishTask() {
    try {
        const response = await fetch(`/finish_task/${taskId}`, {
            method: 'POST',
            credentials: 'include'
        });
        if (response.ok) {
            window.location.href = '/'; // Перенаправление на главную страницу
        }
    } catch (error) {
        console.error('Ошибка при завершении задания:', error);
    }
}

// Инициализация при загрузке страницы
window.onload = async function () {
    // Получаем task_id из URL
    const pathParts = window.location.pathname.split('/');
    taskId = parseInt(pathParts[pathParts.length - 1]);

    if (!taskId) {
        console.error('ID задания не найден в URL');
        return;
    }

    // Загружаем информацию о задании
    await loadTaskInfo();

    // Начинаем задание
    generateTask();
    initWebSocket();

    // Отправляем запрос на начало задания
    try {
        const response = await fetch(`/start_task/${taskId}`, {
            method: 'POST',
            credentials: 'include'
        });
        if (!response.ok) {
            const data = await response.json();
            alert(data.detail || 'Ошибка при начале задания');
        }
    } catch (error) {
        console.error('Ошибка при начале задания:', error);
        alert('Ошибка при начале задания');
    }
};
