# Aviso à Isis — o que esperar da transcrição de áudio (03/08/2026)

> Para o André repassar **antes** de ela testar. O motivo de existir este aviso:
> a transcrição funciona bem o bastante para ela confiar nela — e é justamente
> por isso que o limite precisa ser dito antes, não descoberto depois. Ler um
> bloco de texto fluido e assumir que "quem prometeu" está ali dentro é o erro
> natural a cometer.

---

## A mensagem (pode ser copiada como está)

> Isis, o sistema agora **transcreve** os áudios de reunião que você sobe: o
> arquivo vira texto, e esse texto entra no diagnóstico junto com os documentos
> do caso — dá para citar a reunião como fonte, igual a uma matrícula.
>
> Um limite importante, e é por isso que estou avisando antes: **o sistema
> transcreve o que foi dito, mas ainda não identifica quem disse.** O texto sai
> corrido, sem separar as vozes. Numa conversa entre você e o cliente, as falas
> dos dois ficam na mesma sequência, sem marca de quem é qual.
>
> Então, na prática: **não use o texto para saber quem prometeu o quê.** Ele
> serve para lembrar o que foi tratado, achar um número que foi dito, recuperar
> um detalhe da conversa. Não serve, ainda, para dizer "o cliente se
> comprometeu a mandar o ITR" — isso o texto não distingue.
>
> Estamos medindo uma solução para isso. Até lá, quando a atribuição importar,
> vale registrar à mão.

---

## Se ela perguntar por quê (contexto, não precisa ir junto)

O modelo de transcrição em uso (Whisper) devolve o texto e os tempos de cada
trecho, mas **não devolve quem falou** — isso se chama *diarização* e é um
recurso à parte, que ele não tem. Medimos em 03/08 com duas vozes distintas: a
saída é um bloco só, e a troca de turno não aparece nem como quebra de linha.

O caminho que estamos testando é entregar o áudio ao Gemini (que já usamos em
outras partes do sistema) e pedir que ele marque os falantes. Duas ressalvas que
já sabemos e que vão junto com o resultado:

1. **É um modelo ouvindo e deduzindo, não reconhecimento de voz.** Se ele errar,
   erra como quem entendeu errado — não como quem confundiu duas assinaturas
   vocais. Por isso, quando existir, vai aparecer na tela como *"atribuição
   sugerida"*, para conferência, e nunca como fato.
2. **Atribuição não pode custar vocabulário.** O Whisper só começou a escrever
   "auto de infração" corretamente depois que passamos a lista de termos do
   setor junto do áudio — antes saía "*alto* de infração". Qualquer alternativa
   tem de ser medida também nesse eixo, com o áudio real de uma reunião dela.

## O que ela pode testar agora, com confiança

- Subir a gravação e ver a transcrição pronta na aba Documentos (leva poucos
  minutos; a tela mostra "Transcrevendo o áudio…" enquanto isso).
- Rodar o diagnóstico depois e conferir se o que foi dito na reunião aparece
  considerado, com a reunião citada como fonte.
- Gravação grande ou em formato estranho: **pode subir assim mesmo.** O sistema
  comprime sozinho. Ela só recebe aviso se a gravação passar de uma hora e meia,
  mais ou menos — e aí o pedido é dividir em partes, nada além disso.
- Marcar a gravação como **material interno** (ícone de olho, na linha do
  documento) se aquela conversa não deve aparecer para o cliente no portal.
