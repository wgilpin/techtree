-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Enable Write-Ahead Logging for better concurrency
PRAGMA journal_mode = WAL;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- User assessments table
CREATE TABLE IF NOT EXISTS user_assessments (
    assessment_id TEXT PRIMARY KEY,
    user_id TEXT,
    topic TEXT NOT NULL,
    knowledge_level TEXT NOT NULL,
    score REAL,
    question_history TEXT,  -- JSON text
    response_history TEXT,  -- JSON text
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_assessments_user_id ON user_assessments(user_id);

-- Syllabi table
CREATE TABLE IF NOT EXISTS syllabi (
    syllabus_id TEXT PRIMARY KEY,
    user_id TEXT,
    topic TEXT NOT NULL,
    level TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_syllabi_topic_level ON syllabi(topic, level);
CREATE INDEX IF NOT EXISTS idx_syllabi_user_id ON syllabi(user_id);

-- Modules table
CREATE TABLE IF NOT EXISTS modules (
    module_id INTEGER PRIMARY KEY AUTOINCREMENT,
    syllabus_id TEXT NOT NULL,
    module_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (syllabus_id) REFERENCES syllabi(syllabus_id) ON DELETE CASCADE,
    UNIQUE(syllabus_id, module_index)
);
CREATE INDEX IF NOT EXISTS idx_modules_syllabus_id ON modules(syllabus_id);

-- Lessons table
CREATE TABLE IF NOT EXISTS lessons (
    lesson_id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL,
    lesson_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    duration TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE,
    UNIQUE(module_id, lesson_index)
);
CREATE INDEX IF NOT EXISTS idx_lessons_module_id ON lessons(module_id);

-- Lesson content table
CREATE TABLE IF NOT EXISTS lesson_content (
    content_id TEXT PRIMARY KEY,
    lesson_id INTEGER NOT NULL,
    content TEXT NOT NULL,  -- JSON text
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_lesson_content_lesson_id ON lesson_content(lesson_id);

-- User progress table
CREATE TABLE IF NOT EXISTS user_progress (
    progress_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    syllabus_id TEXT NOT NULL,
    module_index INTEGER NOT NULL,
    lesson_index INTEGER NOT NULL,
    lesson_id INTEGER, -- Added lesson_id column
    status TEXT NOT NULL,  -- "not_started", "in_progress", "completed"
    score REAL,
    lesson_state_json TEXT, -- JSON blob for conversational state (history, mode, etc.)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (syllabus_id) REFERENCES syllabi(syllabus_id) ON DELETE CASCADE,
    FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE, -- Added foreign key
    UNIQUE(user_id, syllabus_id, module_index, lesson_index)
);
CREATE INDEX IF NOT EXISTS idx_progress_user_id ON user_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_progress_syllabus_id ON user_progress(syllabus_id);
CREATE INDEX IF NOT EXISTS idx_progress_user_syllabus ON user_progress(user_id, syllabus_id);
CREATE INDEX IF NOT EXISTS idx_progress_lesson_id ON user_progress(lesson_id); -- Added index for lesson_id