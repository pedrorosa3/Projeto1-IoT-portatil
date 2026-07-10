# Electric Vehicle Charging Infrastructure Management

**Instituição:** Faculdade de Ciências da Universidade de Lisboa (FCUL)  
**Curso:** Mestrado em Engenharia Informática (MEI)  
**Cadeira:** Internet das Coisas (2025/26)  

## 👥 Identificação do Grupo

* **Pedro Rosa** - 60294

## 📌 Visão Geral do Projeto
Este projeto implementa uma plataforma de dados IoT para a monitorização e análise de uma rede de carregamento de veículos elétricos (EVs). A solução permite a recolha, processamento e visualização interativa de dados espaciotemporais relativos às sessões de carregamento, com o objetivo de otimizar operações diárias, identificar padrões de utilização e aplicar modelos de *Machine Learning* (clustering) para agrupar perfis de utilizadores e estações.

## 🏗️ Arquitetura do Sistema
A infraestrutura foi desenhada com base numa arquitetura de microserviços e está totalmente contentorizada utilizando o **Docker Compose**. O ambiente cloud local é composto por cinco serviços principais:

1. **MQTT Broker:** Servidor de mensagens (Mosquitto) configurado no porto 1883 para receção de telemetria dos postos de carregamento.
2. **Processor (Subscriber & ETL):** Serviço responsável por:
   * Subscrever os tópicos MQTT e carregar os datasets *offline*.
   * Interagir com a base de dados para persistência.
   * Invocar o módulo de *Machine Learning*.
   * Atualizar os dados do Dashboard.
3. **Database (DB):** Motor de base de dados relacional ([MySQL / PostgreSQL]) para armazenamento consolidado das sessões de carregamento e gestão da rede.
4. **ML Processor:** Módulo dedicado ao treino e validação de modelos de aprendizagem não supervisionada (clustering) para identificação de padrões e anomalias na infraestrutura.
5. **Dashboard:** Interface de visualização interativa desenvolvida em [Node-RED / outra tecnologia], que expõe métricas em tempo real e análises históricas (ex: energia entregue, tendências de carregamento, custos estimados e perfis de clusters).

*Nota: Todas as comunicações do sistema estão protegidas utilizando TLS (Transport Layer Security) para garantir a confidencialidade e integridade dos dados.*

## 🚀 Como Executar o Projeto

### Pré-requisitos
* [Docker](https://www.docker.com/) e Docker Compose instalados na máquina host.
