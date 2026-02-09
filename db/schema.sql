-- Schema para Journal Intelligence
-- MySQL 8.0+

-- Tabla de revistas/fuentes (sources)
CREATE TABLE IF NOT EXISTS sources (
    source_id VARCHAR(255) PRIMARY KEY,
    display_name VARCHAR(500),
    issn_l VARCHAR(50),
    country_code VARCHAR(10),
    publisher VARCHAR(500),
    type VARCHAR(100),
    works_count INT DEFAULT 0,
    cited_by_count INT DEFAULT 0,
    updated_date DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_display_name (display_name),
    INDEX idx_works_count (works_count),
    INDEX idx_cited_by_count (cited_by_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de trabajos/artículos (works_sample)
CREATE TABLE IF NOT EXISTS works_sample (
    work_id VARCHAR(255) PRIMARY KEY,
    title TEXT,
    publication_year INT,
    cited_by_count INT DEFAULT 0,
    source_id VARCHAR(255),
    source_name VARCHAR(500),
    type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE SET NULL,
    INDEX idx_source_id (source_id),
    INDEX idx_publication_year (publication_year),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de consultas realizadas (query_runs)
CREATE TABLE IF NOT EXISTS query_runs (
    query_id INT AUTO_INCREMENT PRIMARY KEY,
    query_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de recomendaciones generadas (recommendations)
CREATE TABLE IF NOT EXISTS recommendations (
    query_id INT NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    rank_position INT NOT NULL,
    score DECIMAL(10, 4) NOT NULL,
    why TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (query_id, source_id),
    FOREIGN KEY (query_id) REFERENCES query_runs(query_id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE,
    INDEX idx_query_id (query_id),
    INDEX idx_score (score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
