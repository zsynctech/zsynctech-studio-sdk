# ZSync Tech Studio SDK

SDK oficial da ZSync Tech para integração com o ZSync Tech Studio, uma plataforma de automação de processos. Este SDK permite que você desenvolva robôs de automação que se integram perfeitamente com o ecossistema ZSync Tech.

## 📋 Índice

- [Instalação](#instalação)
- [Configuração Inicial](#configuração-inicial)
- [Conceitos Básicos](#conceitos-básicos)
- [Guia de Uso](#guia-de-uso)
  - [StartService - Recebendo Configurações](#startservice---recebendo-configurações)
  - [Execution - Gerenciando Execuções](#execution---gerenciando-execuções)
  - [Task - Gerenciando Tarefas](#task---gerenciando-tarefas)
  - [Step - Gerenciando Passos](#step---gerenciando-passos)
- [Exemplo Completo](#exemplo-completo)
- [API Reference](#api-reference)
- [Dependências](#dependências)
- [Suporte](#suporte)

## 🚀 Instalação via pip

```bash
pip install zsynctech-studio-sdk
```

## 🚀 Instalação via uv

```bash
uv add zsynctech-studio-sdk
```

## ⚙️ Configuração Inicial

Antes de usar o SDK, você precisa configurar suas credenciais:

```python
from zsynctech_studio_sdk import set_credentials

# Configure suas credenciais
set_credentials(
    secret_key="sua_secret_key",
    instance_id="seu_instance_id", 
    server="https://seu-servidor.com"
)
```

## 🧠 Conceitos Básicos

O ZSync Tech Studio SDK trabalha com uma hierarquia de conceitos:

1. **Execution (Execução)**: Representa uma execução completa de um robô
2. **Task (Tarefa)**: Uma tarefa específica dentro de uma execução
3. **Step (Passo)**: Um passo individual dentro de uma tarefa

Cada nível pode ter diferentes status e observações para rastreamento detalhado.

## 📖 Guia de Uso

### StartService - Recebendo Configurações

O `StartService` permite que seu robô receba configurações via RabbitMQ:

```python
from zsynctech_studio_sdk import StartService

# Configure o serviço
start_service = StartService(
    rabbitmq_url="amqp://usuario:senha@servidor:5672/",
    heartbeat=5400
)

# Verificar se há configurações disponíveis
config = start_service.get_start_config()
if config:
    print(f"Execução recebida: {config.executionId}")
    # Processar a configuração...

# Ou usar um listener contínuo
def process_config(config):
    print(f"Processando execução: {config.executionId}")
    # Sua lógica aqui...

start_service.start_listener(process_config)
```

### Execution - Gerenciando Execuções

A classe `Execution` gerencia o ciclo de vida de uma execução:

```python
from zsynctech_studio_sdk import Execution, ExecutionStatus

# Criar uma execução
execution = Execution(config.executionId)

# Iniciar a execução
execution.start("Iniciando processamento...")

# Atualizar progresso
execution.set_total_task_count(100)
execution.update_current_task_count(50)

# Atualizar observação
execution.update_observation("Processando dados...")

# Finalizar com sucesso
execution.finished("Processamento concluído com sucesso!")

# Ou em caso de erro
execution.error("Erro ao processar dados")
```

### Task - Gerenciando Tarefas

A classe `Task` gerencia tarefas individuais:

```python
from zsynctech_studio_sdk import Task

# Criar uma tarefa
task = Task(
    execution_id=execution.execution_id,
    code="TASK_001",
    description="Processar arquivo de dados"
)

# Usar como context manager (recomendado)
with task:
    # Sua lógica aqui
    process_file()
    # Status será automaticamente SUCCESS ou FAIL

# Ou gerenciar manualmente
task.start("Iniciando processamento do arquivo")
try:
    process_file()
    task.success("Arquivo processado com sucesso")
except Exception as e:
    task.fail(f"Erro ao processar arquivo: {str(e)}")
```

### Step - Gerenciando Passos

A classe `Step` gerencia passos individuais dentro de uma tarefa:

```python
from zsynctech_studio_sdk import Step

# Criar um passo
step = Step(
    task_id=task.task_id,
    code="STEP_001",
    observation="Validando dados"
)

# Usar como context manager (recomendado)
with step:
    # Sua lógica aqui
    validate_data()
    # Status será automaticamente SUCCESS ou FAIL

# Ou gerenciar manualmente
step._start("Iniciando validação")
try:
    validate_data()
    step.success("Dados validados com sucesso")
except Exception as e:
    step.fail(f"Erro na validação: {str(e)}")
```

## 💡 Exemplo Completo

```python
from zsynctech_studio_sdk import (
    set_credentials, StartService, Execution, Task, Step
)

# 1. Configurar credenciais
set_credentials(
    secret_key="sua_secret_key",
    instance_id="seu_instance_id",
    server="https://seu-servidor.com"
)

# 2. Configurar StartService
start_service = StartService("amqp://usuario:senha@servidor:5672/")

def process_automation(config):
    """Função principal de processamento"""
    
    # 3. Criar execução
    execution = Execution(config.executionId)
    execution.start("Iniciando automação")
    
    try:
        # 4. Definir total de tarefas
        execution.set_total_task_count(3)
        
        # 5. Processar cada tarefa
        for i, data in enumerate(data_to_process):
            with Task(execution.execution_id, f"TASK_{i:03d}", f"Processar {data}") as task:
                
                # 6. Processar passos da tarefa
                with Step(task.task_id, "VALIDATE", "Validando arquivo") as step:
                    validate_file(data)
                
                with Step(task.task_id, "PROCESS", "Processando dados") as step:
                    process_file(data)
                
                with Step(task.task_id, "SAVE", "Salvando resultado") as step:
                    save_result(data)
                
                # 7. Atualizar progresso
                execution.update_current_task_count(i)
        
        # 8. Finalizar com sucesso
        execution.finished("Automação concluída com sucesso!")
        
    except Exception as e:
        execution.error(f"Erro na automação: {str(e)}")

# 9. Iniciar listener
start_service.start_listener(process_automation)
```

## 📚 API Reference

### StartService

- `__init__(rabbitmq_url: str, heartbeat: int = 5400)`: Inicializa o serviço
- `get_start_config() -> Optional[Config]`: Obtém configuração disponível
- `start_listener(callback: Callable)`: Inicia listener contínuo
- `close()`: Fecha conexão

### Execution

- `start(observation: Optional[str] = None)`: Inicia execução
- `finished(observation: Optional[str] = None)`: Finaliza com sucesso
- `error(observation: Optional[str] = None)`: Marca como erro
- `waiting(observation: Optional[str] = None)`: Marca como aguardando
- `set_total_task_count(count: int)`: Define total de tarefas
- `update_current_task_count(count: int)`: Atualiza progresso
- `update_observation(observation: str)`: Atualiza observação

### Task

- `start(observation: Optional[str] = None)`: Inicia tarefa
- `success(observation: Optional[str] = None)`: Marca como sucesso
- `fail(observation: Optional[str] = None)`: Marca como falha
- Suporte a context manager (`with`)

### Step

- `_start(observation: Optional[str] = None)`: Inicia passo
- `success(observation: Optional[str] = None)`: Marca como sucesso
- `fail(observation: Optional[str] = None)`: Marca como falha
- Suporte a context manager (`with`)

## 📦 Dependências

- `httpx>=0.28.1` - Cliente HTTP
- `pika>=1.3.2` - Cliente RabbitMQ
- `pydantic>=2.11.7` - Validação de dados
- `rich>=14.1.0` - Interface rica
- `uuid7>=0.1.0` - Geração de UUIDs

## 🆘 Suporte

Para suporte técnico, entre em contato:

- **Email**: contato@zsynctech.com
- **Empresa**: ZSync Tech LTDA

---

**Versão**: 0.1.0  
**Python**: >=3.13
