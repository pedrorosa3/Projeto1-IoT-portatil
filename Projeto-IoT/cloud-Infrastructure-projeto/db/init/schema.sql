-- ==========================================================
-- SCHEMA: Plataforma IoT para Rede de Carregamento EV
-- MySQL 8.x / MariaDB compatível
-- ==========================================================

-- garantir que existe base de dados
CREATE DATABASE IF NOT EXISTS evcharging;
USE evcharging;

-- ==========================================================
-- 1. Tabela de utilizadores e veículo associado
-- ==========================================================
DROP TABLE IF EXISTS ev_users;

CREATE TABLE ev_users (
    user_id                INT AUTO_INCREMENT PRIMARY KEY,
    user_code              VARCHAR(50) UNIQUE ,     -- "User ID" do Excel
    vehicle_model          VARCHAR(100),                    -- "Vehicle Model"
    battery_capacity_kwh   DECIMAL(10,2),                   -- "Battery Capacity (kWh)"
    vehicle_age_years      DECIMAL(5,2),                    -- "Vehicle Age (years)"
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ==========================================================
-- 2. Tabela de estações de carregamento
-- ==========================================================
DROP TABLE IF EXISTS stations;

CREATE TABLE stations (
    station_id          INT AUTO_INCREMENT PRIMARY KEY,
    station_code        VARCHAR(50) UNIQUE NOT NULL,        -- "Charging Station ID"
    distrito            VARCHAR(100),                       -- Dataset #3
    concelho            VARCHAR(100),
    freguesia           VARCHAR(100),
    latitude            DECIMAL(10,6) NOT NULL,
    longitude           DECIMAL(10,6) NOT NULL,
    power_kw            INT,                                -- "Potência Máxima Admissível (kW)"
    connection_points   INT,                                -- "Pontos de ligação para instalações PCVE"
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ==========================================================
-- 3. Tabela de sessões de carregamento
-- ==========================================================
DROP TABLE IF EXISTS sessions;

CREATE TABLE sessions (
    session_id      BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- foreign keys
    user_id         INT NULL,
    station_id      INT NOT NULL,

    -- timestamps
    start_time      DATETIME ,
    end_time        DATETIME,

    -- métricas principais
    energy_kwh      DECIMAL(10,2),
    duration_h      DECIMAL(10,2),         -- "Charging Duration (hours)"
    rate_kw         DECIMAL(10,2),         -- "Charging Rate (kW)"
    estimated_cost  DECIMAL(10,2),         -- "Charging Cost (EUR)"

    -- indicadores contextuais (para clustering e analytics)
    time_of_day     VARCHAR(20),           -- Morning / Afternoon / Night / etc.
    day_of_week     VARCHAR(20),           -- Monday / Tuesday / etc.
    soc_start       INT,                   -- "State of Charge (Start %)"
    soc_end         INT,                   -- "State of Charge (End %)"
    distance_km     DECIMAL(10,2),         -- "Distance Driven (since last charge)"
    temperature_c   DECIMAL(10,2),

    -- indica fonte: offline ou streaming MQTT
    source          ENUM('offline', 'mqtt') DEFAULT 'offline',

    -- constraints
    FOREIGN KEY (user_id) REFERENCES ev_users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (station_id) REFERENCES stations(station_id) ON DELETE CASCADE
);


-- ==========================================================
-- INDEXES OTIMIZADORES (para dashboards e ML)
-- ==========================================================
CREATE INDEX idx_sessions_station ON sessions (station_id);
CREATE INDEX idx_sessions_user ON sessions (user_id);
CREATE INDEX idx_sessions_start_time ON sessions (start_time);
