from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import httpx

app = FastAPI()

# Simula armazenamento de estado por telefone
usuarios = {}

# Fluxo de mensagens via Twilio WhatsApp
@app.post("/")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    telefone = form.get("From")  # ex: whatsapp:+5511999999999
    mensagem = (form.get("Body") or "").strip()
    num_media = int(form.get("NumMedia", 0))

    usuario = usuarios.get(telefone, {"etapa": "inicio"})

    # Novo usuário: começa o fluxo de cadastro
    if usuario["etapa"] == "inicio":
        usuarios[telefone] = {"etapa": "nome"}
        return xml_response("Oi! Seja bem-vindo ao Blinkpay.\nNão encontramos um cadastro seu ainda, tudo bem se começarmos agora? Qual seu nome?")

    elif usuario["etapa"] == "nome":
        usuario["nome"] = mensagem
        usuario["etapa"] = "cpf"
        return xml_response(f"Legal! Para começarmos, qual é o seu nome?\n\nPrazer, {mensagem}! Agora, poderia me informar seu CPF?")

    elif usuario["etapa"] == "cpf":
        usuario["cpf"] = mensagem
        usuario["etapa"] = "foto"
        return xml_response("Perfeito!\nGostaria de tirar uma foto agora para vincular ao seu perfil? Se sim, envie a foto aqui.")

    elif usuario["etapa"] == "foto":
        if num_media > 0:
            media_url = form.get("MediaUrl0")
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(media_url)
                    image_bytes = response.content

                import boto3
                rekognition = boto3.client("rekognition", region_name="us-east-1")
                external_image_id = usuario.get("nome", telefone).replace(" ", "_")
                rekognition.index_faces(
                    CollectionId="blinkpay",
                    Image={"Bytes": image_bytes},
                    ExternalImageId=external_image_id,
                    DetectionAttributes=["ALL"]
                )
                usuario["etapa"] = "dependente"
                return xml_response("Foto recebida com sucesso e cadastrada no sistema!\nVocê quer adicionar algum dependente à sua conta? Pode ser filho, parceiro, etc. (Responda sim ou não)")
            except Exception as e:
                return xml_response(f"Ocorreu um erro ao cadastrar sua foto. Tente novamente. Erro: {str(e)}")
        else:
            return xml_response("Por favor, envie a foto para continuar.")

    elif usuario["etapa"] == "dependente":
        if mensagem.lower() in ["sim", "s"]:
            usuario["etapa"] = "cadastrando_dependente"
            return xml_response("Sem problemas! Vamos cadastrar os dados dele(a). Qual o nome do dependente?")
        else:
            usuario["etapa"] = "finalizado"
            usuario["pix"] = "blinkpix123@blinkpay.com.br"
            return xml_response(f"Tudo certo por aqui!\nSua chave Pix para adicionar saldo na sua conta é: {usuario['pix']}")

    elif usuario["etapa"] == "cadastrando_dependente":
        dependentes = usuario.get("dependentes", [])
        dependentes.append({"nome": mensagem})
        usuario["dependentes"] = dependentes
        usuario["etapa"] = "finalizado"
        usuario["pix"] = "blinkpix123@blinkpay.com.br"
        return xml_response(f"Dependente cadastrado!\nSua chave Pix para adicionar saldo na sua conta é: {usuario['pix']}")

    elif usuario["etapa"] == "finalizado":
        nome = usuario.get("nome", "usuário")
        # Aqui você poderia chamar seu backend para saldo real
        saldo = 123.45
        return xml_response(
            f"Olá, {nome}! Bom te ver de novo.\nNo momento, você tem R$ {saldo:.2f} disponíveis na sua conta.\n\n"
            "O que você gostaria de fazer agora?\n"
            "1. Ver minha chave Pix para depósito\n"
            "2. Tirar uma nova foto de perfil\n"
            "3. Gerenciar meus dependentes (adicionar ou remover)\n"
            "4. Outra coisa"
        )

    # Salva atualização do usuário
    usuarios[telefone] = usuario
    return xml_response("Desculpe, não entendi. Pode repetir?")

def xml_response(message: str) -> PlainTextResponse:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""
    return PlainTextResponse(xml, media_type="application/xml")