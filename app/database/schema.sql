CREATE TABLE IF NOT EXISTS usuarios (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(80) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol ENUM('profesor', 'estudiante') NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash CHAR(64) PRIMARY KEY,
    usuario_id BIGINT UNSIGNED NOT NULL,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_session_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS login_attempts (
    attempt_key CHAR(64) PRIMARY KEY,
    failures INT UNSIGNED NOT NULL DEFAULT 0,
    window_started DATETIME NOT NULL,
    locked_until DATETIME NULL,
    INDEX idx_attempt_window (window_started)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS torneos (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    slug VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS inscripciones (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    torneo_id BIGINT UNSIGNED NOT NULL,
    usuario_id BIGINT UNSIGNED NOT NULL,
    nombre VARCHAR(60) NOT NULL,
    curso VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY equipo_unico (torneo_id, nombre, curso),
    FOREIGN KEY (torneo_id) REFERENCES torneos(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    INDEX idx_inscripcion_usuario (usuario_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS partidos (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    torneo_id BIGINT UNSIGNED NOT NULL,
    fase ENUM('semifinal1', 'semifinal2', 'final') NOT NULL,
    equipo_a_id BIGINT UNSIGNED NULL,
    equipo_b_id BIGINT UNSIGNED NULL,
    ganador_id BIGINT UNSIGNED NULL,
    UNIQUE KEY partido_unico (torneo_id, fase),
    FOREIGN KEY (torneo_id) REFERENCES torneos(id),
    FOREIGN KEY (equipo_a_id) REFERENCES inscripciones(id),
    FOREIGN KEY (equipo_b_id) REFERENCES inscripciones(id),
    FOREIGN KEY (ganador_id) REFERENCES inscripciones(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
