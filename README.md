🌌 Kc Studio 4.19.2

A IDE Python Híbrida impulsionada por I.A. (Google Gemini)
O Kymera Coder não é apenas um editor de código; é uma Estação de Desenvolvimento Inteligente construída para desenvolvedores Python que buscam produtividade máxima.

Com uma interface inspirada no clássico VS Code Dark Theme e integração direta e assíncrona com o Google Gemini 2.5, o Kymera atua como o seu Pair Programmer Sênior.

⚡ O Que Há de Novo na 4.19.1?
Motor Neural Aprimorado: Integração direta com a nova biblioteca google-genai. Respostas mais rápidas e códigos mais otimizados usando a versão gemini-2.5-flash.

Terminal Interativo Embutido (PTY): Adeus janelas pretas irritantes saltando na tela. Comandos do Windows (pip install, dir, execução de scripts de texto) rodam nativamente dentro do terminal da IDE. Interfaces Gráficas abrem nativamente no OS.
Line Numbers (Numeração de Linhas): Rastreador de linhas dinâmico acoplado ao editor para facilitar o debug.
Aba de Problemas Isolada: O Terminal agora separa o que é "Trabalho" do que é "Erro de Sintaxe".
Compilador .EXE Oculto: O Kymera embutiu o motor do PyInstaller. Um clique, e o seu código Python vira um arquivo Windows executável.

🛠️ Recursos e Ferramentas Embutidas

🧠 Copilot I.A. Integrado
O Kymera possui uma aba dedicada de inteligência. A I.A. possui Memória de Sessão, ou seja, ela se lembra das variáveis e do escopo que você discutiu nos chats anteriores.
Auto-Leitura de Código: Pergunte "Ache o bug" e o Kymera automaticamente fará o parse do que está escrito no seu editor atual e enviará à I.A., inserindo a correção na sua tela com um clique.
🎨 Syntax Highlighting & Dark Theme
Cores sintáticas idênticas aos padrões comerciais. Suporte a quebra de linha fluida (Word Wrap) e busca (Find/Replace).

🖱️ Drag & Drop
Trabalhando com um projeto antigo? Simplesmente arraste o arquivo .py da sua área de trabalho para dentro do editor e comece a digitar.

⌨️ Atalhos de Produtividade (Shortcuts)

Ação	Atalho de Teclado
Completar Código (IntelliSense Base)	TAB (Ao digitar parte da variável)

Comentar/Descomentar Bloco	Ctrl + /

Duplicar Linha Atual	Ctrl + D

Voltar Ação (Undo)	Ctrl + Z

⚙️ Instalação e Requisitos

O Kymera Coder é leve, não utiliza Electron e foi escrito inteiramente em Python moderno (PyQt6).

1. Dependências do Sistema
Certifique-se de ter o Python (3.10 ou superior) instalado no seu computador.

Abra o seu terminal nativo e instale os motores gráficos e de IA:

code:

Bash
pip install PyQt6 google-genai pyinstaller

(O pyinstaller só é necessário se você desejar exportar seus códigos como aplicativos .EXE).

3. Configurando a API Key
   
Para que a Inteligência Artificial do Kymera ganhe vida:

Acesse o Google AI Studio.

Faça login e gere uma API Key gratuitamente.
Cole a chave na barra superior do Kymera Coder e clique em "Conectar".

🔒 Segurança e Continuidade: O Kymera utiliza o "Cofre do Sistema" (QSettings). Ao colar sua chave e programar, você pode fechar o aplicativo sem medo. Ao abrir novamente, o Kymera recarregará seu último código, seu chat e sua API Key automaticamente.

🚀 Como Executar

Após instalar as dependências, clone ou baixe o arquivo principal kymera_coder.py.
No seu terminal, digite:
code
Bash
pythonKc Studio 4.19.2.py

Desenvolvido por Kymera Coder 
