<div align="center">

# ⚡ Gestão de Infraestrutura de Carregamento de Veículos Elétricos

**Plataforma IoT para monitorização, análise e *clustering* de uma rede de postos de carregamento de VEs**

![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?logo=eclipsemosquitto&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white)
![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)
![Node-RED](https://img.shields.io/badge/Node--RED-Dashboard-8F0000?logo=nodered&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-KMeans-F7931E?logo=scikitlearn&logoColor=white)

</div>

---

## 📋 Informação Geral

| | |
|---|---|
| **Instituição** | Faculdade de Ciências da Universidade de Lisboa (FCUL) |
| **Curso** | Mestrado em Engenharia Informática (MEI) |
| **Unidade Curricular** | Internet das Coisas — 2025/26 |
| **Grupo** | 23 |
| **Autores** | Pedro Rosa (60294) · Hugo Silva |
| **Data** | Novembro de 2025 |

---

## 📌 Visão Geral

Este projeto implementa uma plataforma de dados IoT para a monitorização e análise de uma rede de carregamento de veículos elétricos. A solução recolhe, processa e apresenta de forma interativa dados espaciotemporais das sessões de carregamento, com o objetivo de:

- 📊 Otimizar as operações diárias da rede;
- 🔍 Identificar padrões de utilização;
- 🤖 Aplicar *Machine Learning* não supervisionado (**K-Means**) para agrupar perfis de estações e de sessões de carregamento.

---

## 🏗️ Arquitetura

Toda a infraestrutura assenta numa arquitetura de microserviços, contentorizada com **Docker Compose**.

```
┌──────────────┐   MQTT/TLS (8883)   ┌──────────────┐
│ simulator.py │ ──────────────────► │ mqtt-broker  │
│  (host)      │  iot/ev-station     │  Mosquitto   │
└──────────────┘                     └──────┬───────┘
                                            │
                     ┌──────────────────────┼─────────────────────┐
                     ▼                                            ▼
             ┌──────────────┐  iot/ev-station/ml/run     ┌──────────────┐
             │  processor   │ ─────────────────────────► │ ml-processor │
             │ (ETL + MQTT) │                            │  (K-Means)   │
             └──────┬───────┘                            └──────┬───────┘
                    │                                           │
                    ▼                                           ▼
             ┌──────────────────────────────────────────────────────┐
             │                 database (MySQL)                      │
             │              ev_charging_db : 3306                    │
             └──────────────────────────┬───────────────────────────┘
                                        ▼
                               ┌──────────────────┐
                               │    dashboard     │
                               │ Node-RED : 1880  │
                               └──────────────────┘
```

| Serviço | Tecnologia | Porto(s) | Função |
|---|---|---|---|
| `mqtt-broker` | Eclipse Mosquitto | `1883`, `8883` (TLS) | Recebe a telemetria dos postos de carregamento |
| `processor` | Python | — | Carrega os datasets *offline*, subscreve `iot/ev-station`, persiste na BD e despoleta o ML |
| `database` | MySQL | `3306` | Armazena estações (`ev_stations`) e sessões (`charging`) |
| `ml-processor` | Python + scikit-learn | — | Treina/atualiza modelos K-Means de estações e sessões |
| `dashboard` | Node-RED + FlowFuse Dashboard + Worldmap | `1880` | Visualização em tempo real e histórica |

### 📦 Versões utilizadas

As versões estão fixas para que o projeto se comporte sempre da mesma forma:

| Componente | Versão |
|---|---|
| Eclipse Mosquitto | `2.0.22` |
| MySQL | `26.10.0` |
| Node-RED | `4.1.1` |
| Python (imagens dos serviços) | `3.10.22-slim` |
| pandas · scikit-learn · paho-mqtt · mysql-connector-python | `2.3.3` · `1.7.2` · `1.6.1` · `26.10.0` |

> 🔒 As comunicações MQTT entre serviços usam **TLS** (porto `8883`), com certificados próprios em [`ev-iot-project/Certificates/`](ev-iot-project/Certificates/).

---

## 📁 Estrutura do Repositório

```
ev-iot-project/
├── Certificates/          # CA e certificados TLS do broker
├── EVDataset/             # Datasets CSV (estações, histórico e simulação online)
├── MLprocessor/           # Serviço de Machine Learning (K-Means)
├── MQTTprocessor/         # Serviço de ingestão / ETL
├── mosquitto/config/      # Configuração do broker
├── node_red_data/         # Flows e configuração do dashboard
├── docker-compose.yml     # Orquestração de todos os serviços
├── simulator.py           # Simulador de postos de carregamento
└── IdC-2526-Project-Group23.pdf   # Relatório do projeto
```

---

## 🚀 Como Executar

### Pré-requisitos

- [Docker](https://www.docker.com/) e **Docker Compose**
- [Python 3](https://www.python.org/) (apenas para correr o simulador no host)

### 1. Clonar o repositório

```bash
git clone https://github.com/pedrorosa3/Projeto1-IoT-portatil.git
cd Projeto1-IoT-portatil/ev-iot-project
```

### 2. Levantar a infraestrutura

```bash
docker compose up -d --build
```

Isto constrói as imagens do `processor` e do `ml-processor` e arranca os cinco serviços. No primeiro arranque:

- o `dashboard` instala automaticamente os plugins do Node-RED (FlowFuse Dashboard, Worldmap e MySQL);
- o `processor` e o `ml-processor` esperam que o MySQL fique *healthy*;
- o `processor` cria as tabelas e carrega os dados históricos de `EVDataset/`;
- o `ml-processor` treina os modelos K-Means de estações, sessões e horários.

O primeiro arranque demora cerca de **1 a 2 minutos**.

Para acompanhar os logs:

```bash
docker compose logs -f processor ml-processor
```

> ⚠️ **Porto 3306 ocupado?** Se já tiveres um MySQL instalado localmente, o contentor `database` não arranca (`ports are not available`). Para resolver, pára o serviço local ou altera em `docker-compose.yml` o mapeamento `3306:3306` para, por exemplo, `3307:3306`. Os restantes serviços comunicam pela rede interna do Docker e não são afetados.

### 3. Abrir o Dashboard

| Recurso | URL |
|---|---|
| Dashboard | <http://localhost:1880/dashboard/> |
| Editor Node-RED | <http://localhost:1880> |

### 4. Iniciar a simulação em tempo real

Numa nova janela de terminal, ainda dentro de `ev-iot-project/`:

```bash
pip install pandas "paho-mqtt==1.6.1"
python simulator.py
```

O simulador lê `EVDataset/dataset-EV_with_stations_for_online_simulation.csv` e publica uma sessão de carregamento a cada **30 segundos** no tópico `iot/ev-station`, através de TLS (`localhost:8883`). Cada nova mensagem é guardada na base de dados e volta a despoletar o modelo de ML, atualizando o dashboard.

### 5. Parar o sistema

```bash
docker compose down        # pára os serviços
docker compose down -v     # pára e apaga também os dados da BD
```

---

## 🔌 Tópicos MQTT

| Tópico | Publicador | Subscritor | Descrição |
|---|---|---|---|
| `iot/ev-station` | `simulator.py` | `processor` | Dados de cada sessão de carregamento (JSON) |
| `iot/ev-station/ml/run` | `processor` | `ml-processor` | Pedido de (re)treino / atualização dos clusters |

---

## 👥 Autores

- **Pedro Rosa** — 60294
- **Hugo Silva**

<div align="center">

*FCUL · Internet das Coisas · Novembro de 2025*

</div>
