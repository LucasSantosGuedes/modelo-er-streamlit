import streamlit as st
import requests

st.set_page_config(page_title="Modelagem e Normalização de Dados", layout="wide")
st.title("🗂️ Diagrama Fácil")

# Função para gerar SQL no padrão Oracle
def generate_sql(entities, relationships):
    sql_statements = []
    sequence_statements = []
    for entity_name, entity in entities.items():
        attrs = entity['attributes']
        is_weak = entity['is_weak']
        supertype = entity['supertype']
        subtypes = entity['subtypes']
        
        sql = f"CREATE TABLE {entity_name} (\n"
        pk_attrs = [attr['name'] for attr in attrs if attr['is_primary_key']]
        fk_statements = []
        for attr in attrs:
            line = f"    {attr['name']} {attr['data_type']}"
            if attr['is_primary_key'] and not is_weak:
                line += " PRIMARY KEY"
            if attr['is_multivalued']:
                # Em Oracle, atributos multivalorados podem ser modelados em tabelas separadas
                multivalued_table = f"{entity_name}_{attr['name']}"
                multivalued_sql = f"CREATE TABLE {multivalued_table} (\n"
                multivalued_sql += f"    {entity_name}_id {entities[entity_name]['primary_key_type']},\n"
                multivalued_sql += f"    {attr['name']} {attr['data_type']},\n"
                multivalued_sql += f"    FOREIGN KEY ({entity_name}_id) REFERENCES {entity_name}({pk_attrs[0]})\n"
                multivalued_sql += ");\n"
                sql_statements.append(multivalued_sql)
                continue  # Não incluir o atributo na tabela principal
            if attr['is_derived']:
                # Atributos derivados não são armazenados no banco, podem ser calculados via VIEW
                continue
            sql += line + ",\n"
            if attr['is_foreign_key']:
                fk = f"FOREIGN KEY ({attr['name']}) REFERENCES {attr['references']}({attr['referenced_attr']})"
                fk_statements.append(fk)
        # Remover a última vírgula
        sql = sql.rstrip(",\n") + "\n"
        if is_weak:
            # Chave primária composta para entidades fracas
            pk = ", ".join(pk_attrs)
            sql += f",    PRIMARY KEY ({pk})\n"
        if fk_statements:
            sql += ",\n    " + ",\n    ".join(fk_statements) + "\n"
        sql += ");\n"
        sql_statements.append(sql)

        # Criar sequência para chave primária se for numérica
        for attr in attrs:
            if attr['is_primary_key'] and attr['data_type'].upper() in ('NUMBER', 'INT', 'INTEGER'):
                sequence_name = f"{entity_name}_{attr['name']}_seq"
                sequence_sql = f"CREATE SEQUENCE {sequence_name} START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;"
                sequence_statements.append(sequence_sql)
                break  # Considerando apenas uma sequência por tabela

    # Adicionar relacionamentos
    for rel in relationships:
        if rel["relationship_type"] == "1:N":
            # Adicionar FK na tabela "N"
            fk_attr = f"{rel['entity1']}_id"
            fk_sql = f"ALTER TABLE {rel['entity2']} ADD ({fk_attr} {entities[rel['entity1']]['primary_key_type']});\n"
            fk_sql += f"ALTER TABLE {rel['entity2']} ADD CONSTRAINT fk_{rel['entity2']}_{rel['entity1']} FOREIGN KEY ({fk_attr}) REFERENCES {rel['entity1']}({entities[rel['entity1']]['primary_key']});\n"
            sql_statements.append(fk_sql)
        elif rel["relationship_type"] == "N:N":
            # Criar tabela associativa
            assoc_table = f"{rel['entity1']}_{rel['entity2']}"
            pk1 = entities[rel['entity1']]['primary_key']
            pk2 = entities[rel['entity2']]['primary_key']
            pk1_type = entities[rel['entity1']]['primary_key_type']
            pk2_type = entities[rel['entity2']]['primary_key_type']
            sql = f"CREATE TABLE {assoc_table} (\n"
            sql += f"    {rel['entity1']}_id {pk1_type},\n"
            sql += f"    {rel['entity2']}_id {pk2_type},\n"
            sql += f"    PRIMARY KEY ({rel['entity1']}_id, {rel['entity2']}_id),\n"
            sql += f"    FOREIGN KEY ({rel['entity1']}_id) REFERENCES {rel['entity1']}({pk1}),\n"
            sql += f"    FOREIGN KEY ({rel['entity2']}_id) REFERENCES {rel['entity2']}({pk2})\n"
            sql += ");\n"
            sql_statements.append(sql)
        elif rel["relationship_type"] == "1:1":
            # Em relacionamentos 1:1, a chave estrangeira pode ficar em qualquer tabela
            fk_attr = f"{rel['entity1']}_id"
            fk_sql = f"ALTER TABLE {rel['entity2']} ADD ({fk_attr} {entities[rel['entity1']]['primary_key_type']} UNIQUE);\n"
            fk_sql += f"ALTER TABLE {rel['entity2']} ADD CONSTRAINT fk_{rel['entity2']}_{rel['entity1']} FOREIGN KEY ({fk_attr}) REFERENCES {rel['entity1']}({entities[rel['entity1']]['primary_key']});\n"
            sql_statements.append(fk_sql)
    # Retornar sequência e statements
    return "\n".join(sequence_statements + sql_statements)

# Função para gerar diagrama PlantUML
def generate_plantuml_diagram(entities, relationships):
    uml = "@startuml\n!define ER_TOP_DOWN\n' Configurações de estilo\nhide circle\nskinparam linetype ortho\n"
    # Definir entidades e seus atributos
    for entity_name, entity in entities.items():
        attrs = entity['attributes']
        uml += f"entity \"{entity_name}\" as {entity_name} {{\n"
        for attr in attrs:
            if attr['is_primary_key']:
                uml += f"  * {attr['name']} : {attr['data_type']}\n"  # Chave primária
            elif attr['is_foreign_key']:
                uml += f"  + {attr['name']} : {attr['data_type']}\n"  # Chave estrangeira
            else:
                uml += f"  {attr['name']} : {attr['data_type']}\n"
        uml += "}\n"
        # Generalização/especialização
        if entity['supertype']:
            uml += f"{entity_name} --|> {entity['supertype']}\n"
        for subtype in entity['subtypes']:
            uml += f"{subtype} --|> {entity_name}\n"
    # Definir relacionamentos
    for rel in relationships:
        ent1 = rel['entity1']
        ent2 = rel['entity2']
        rel_name = rel['relationship_name']
        rel_type = rel['relationship_type']
        if rel_type == '1:1':
            uml += f"{ent1} ||--|| {ent2} : \"{rel_name}\"\n"
        elif rel_type == '1:N':
            uml += f"{ent1} ||--o{{ {ent2} : \"{rel_name}\"\n"
        elif rel_type == 'N:N':
            uml += f"{ent1} }}o--o{{ {ent2} : \"{rel_name}\"\n"
    uml += "@enduml"
    return uml

# Sessão 1: Definição das Entidades
st.header("1. Definir Entidades")
st.write("Insira as entidades principais e suas características.")

# Explicação opcional sobre Entidades
with st.expander("📖 O que é uma Entidade?"):
    st.write("""
    Uma **entidade** é um objeto ou conceito sobre o qual você deseja armazenar informações no banco de dados.
    Exemplos incluem **Cliente**, **Produto**, **Pedido**, etc.
    """)

if 'entities' not in st.session_state:
    st.session_state.entities = {}

with st.form("entity_form", clear_on_submit=True):
    entity_name = st.text_input("Nome da Entidade", placeholder="Exemplo: Cliente")
    is_weak = st.checkbox("Entidade Fraca?")
    supertype = st.selectbox("Especialização de", ["Nenhum"] + list(st.session_state.entities.keys()))
    submitted = st.form_submit_button("Adicionar Entidade")
    if submitted:
        if entity_name:
            if entity_name in st.session_state.entities:
                st.warning(f"A entidade '{entity_name}' já existe.")
            else:
                st.session_state.entities[entity_name] = {
                    'attributes': [],
                    'is_weak': is_weak,
                    'supertype': supertype if supertype != "Nenhum" else None,
                    'subtypes': [],
                    'primary_key': None,
                    'primary_key_type': None
                }
                if supertype != "Nenhum":
                    st.session_state.entities[supertype]['subtypes'].append(entity_name)
                st.success(f"Entidade '{entity_name}' adicionada com sucesso!")
        else:
            st.error("Por favor, preencha o nome da entidade.")

# Sessão para adicionar atributos às entidades
st.header("1.1. Definir Atributos das Entidades")
st.write("Adicione atributos às entidades definidas.")

if st.session_state.entities:
    entity_to_edit = st.selectbox("Selecionar Entidade", list(st.session_state.entities.keys()))
    with st.form("attribute_form", clear_on_submit=True):
        attr_name = st.text_input("Nome do Atributo", placeholder="Exemplo: id_cliente")
        attr_type = st.selectbox("Tipo de Dado", ["VARCHAR2(255)", "NUMBER", "DATE", "CHAR(1)", "CLOB", "BLOB"])
        is_primary_key = st.checkbox("Chave Primária?")
        is_foreign_key = st.checkbox("Chave Estrangeira?")
        is_multivalued = st.checkbox("Atributo Multivalorado?")
        is_derived = st.checkbox("Atributo Derivado?")
        submitted_attr = st.form_submit_button("Adicionar Atributo")
        if submitted_attr:
            if attr_name and attr_type:
                attribute = {
                    'name': attr_name,
                    'data_type': attr_type,
                    'is_primary_key': is_primary_key,
                    'is_foreign_key': is_foreign_key,
                    'is_multivalued': is_multivalued,
                    'is_derived': is_derived,
                    'references': None,
                    'referenced_attr': None
                }
                if is_primary_key:
                    if st.session_state.entities[entity_to_edit]['primary_key']:
                        st.warning(f"A entidade '{entity_to_edit}' já possui uma chave primária.")
                    else:
                        st.session_state.entities[entity_to_edit]['primary_key'] = attr_name
                        st.session_state.entities[entity_to_edit]['primary_key_type'] = attr_type
                if is_foreign_key:
                    ref_entity = st.selectbox("Referenciar Entidade", list(st.session_state.entities.keys()))
                    ref_attr = st.selectbox("Referenciar Atributo", [attr['name'] for attr in st.session_state.entities[ref_entity]['attributes'] if attr['is_primary_key']])
                    attribute['references'] = ref_entity
                    attribute['referenced_attr'] = ref_attr
                st.session_state.entities[entity_to_edit]['attributes'].append(attribute)
                st.success(f"Atributo '{attr_name}' adicionado à entidade '{entity_to_edit}'.")
            else:
                st.error("Por favor, preencha o nome do atributo e selecione o tipo de dado.")

    # Exibir atributos da entidade selecionada
    st.subheader(f"Atributos da Entidade '{entity_to_edit}':")
    for attr in st.session_state.entities[entity_to_edit]['attributes']:
        details = f"{attr['name']} ({attr['data_type']})"
        if attr['is_primary_key']:
            details += " [PK]"
        if attr['is_foreign_key']:
            details += f" [FK -> {attr['references']}({attr['referenced_attr']})]"
        if attr['is_multivalued']:
            details += " [Multivalorado]"
        if attr['is_derived']:
            details += " [Derivado]"
        st.write(details)

# Sessão 2: Definir Relacionamentos
st.header("2. Definir Relacionamentos")
st.write("Escolha duas entidades e defina o tipo de relacionamento entre elas.")

# Explicação opcional sobre Relacionamentos
with st.expander("📖 O que é um Relacionamento?"):
    st.write("""
    Um **relacionamento** define como duas entidades estão associadas no modelo de dados.
    Exemplos:
    - Um **Cliente** faz um **Pedido**
    - Um **Pedido** contém **Produtos**
    - Um **Funcionário** gerencia um **Departamento**

    **Tipos de Relacionamentos:**
    - **1:1 (Um para Um):** Uma instância de uma entidade está relacionada a uma instância de outra entidade.
    - **1:N (Um para Muitos):** Uma instância de uma entidade está relacionada a múltiplas instâncias de outra entidade.
    - **N:N (Muitos para Muitos):** Múltiplas instâncias de uma entidade estão relacionadas a múltiplas instâncias de outra entidade.
    """)

if 'relationships' not in st.session_state:
    st.session_state.relationships = []

if len(st.session_state.entities) >= 2:
    with st.form("relationship_form", clear_on_submit=True):
        entity_1 = st.selectbox("Entidade 1", list(st.session_state.entities.keys()))
        entity_2 = st.selectbox("Entidade 2", list(st.session_state.entities.keys()))
        relationship_type = st.radio("Tipo de Relacionamento", ["1:1", "1:N", "N:N"])
        relationship_name = st.text_input(
            "Nome do Relacionamento",
            placeholder="Exemplo: realiza, contém, gerencia"
        )
        participation = st.radio("Participação da Entidade 1", ["Total", "Parcial"])
        participation2 = st.radio("Participação da Entidade 2", ["Total", "Parcial"])
        # Explicação opcional sobre o Nome do Relacionamento
        with st.expander("📖 O que é o 'Nome do Relacionamento'?"):
            st.write("""
            O **"Nome do Relacionamento"** descreve como as duas entidades estão conectadas ou interagem no seu modelo de dados. Pense em verbos ou frases que indicam a ação ou a associação entre elas.

            **Exemplos de Nomes de Relacionamento:**
            - **Cliente** **realiza** **Pedido**
            - **Pedido** **contém** **Produto**
            - **Funcionário** **gerencia** **Departamento**
            """)
        submitted_rel = st.form_submit_button("Adicionar Relacionamento")
        if submitted_rel:
            if entity_1 and entity_2 and relationship_name:
                if entity_1 == entity_2:
                    st.error("Não é permitido relacionar uma entidade consigo mesma.")
                else:
                    # Verificar se o relacionamento já existe
                    exists = False
                    for rel in st.session_state.relationships:
                        if (rel["entity1"] == entity_1 and rel["entity2"] == entity_2 and rel["relationship_name"] == relationship_name):
                            exists = True
                            break
                    if exists:
                        st.warning("Este relacionamento já foi adicionado.")
                    else:
                        st.session_state.relationships.append({
                            "entity1": entity_1,
                            "entity2": entity_2,
                            "relationship_name": relationship_name,
                            "relationship_type": relationship_type,
                            "participation": participation,
                            "participation2": participation2
                        })
                        st.success(f"Relacionamento '{entity_1} - {relationship_name} - {entity_2}' adicionado com sucesso!")
            else:
                st.error("Por favor, preencha todas as informações do relacionamento.")

# Exibir relacionamentos definidos
if st.session_state.relationships:
    st.subheader("Relacionamentos Definidos:")
    for rel in st.session_state.relationships:
        st.markdown(f"**{rel['entity1']}** ({rel['participation']}) {rel['relationship_type']} **{rel['relationship_name']}** **{rel['entity2']}** ({rel['participation2']})")

# Sessão 3: Gerar Diagrama e SQL
st.header("3. Gerar Diagrama, Modelo Lógico e SQL")

col1, col2 = st.columns(2)

with col1:
    if st.button("Gerar Diagrama e Modelo Lógico"):
        if not st.session_state.entities:
            st.error("Adicione pelo menos uma entidade para gerar o diagrama.")
        else:
            # Gerar Diagrama ER usando PlantUML via Kroki API
            plantuml_code = generate_plantuml_diagram(st.session_state.entities, st.session_state.relationships)
            st.session_state.plantuml_code = plantuml_code

            # Enviar código para a API do Kroki
            url = "https://kroki.io/plantuml/png"
            response = requests.post(url, data=plantuml_code.encode('utf-8'))

            if response.status_code == 200:
                st.subheader("Diagrama ER")
                st.image(response.content)
                st.session_state.diagram_image = response.content  # Armazenar a imagem no session_state
            else:
                st.error("Erro ao gerar o diagrama.")

            # Geração do Modelo Lógico
            st.subheader("Modelo Lógico")
            logical_model = ""
            for entity_name, entity in st.session_state.entities.items():
                logical_model += f"**Tabela `{entity_name}`**\n"
                for attr in entity['attributes']:
                    details = f"- `{attr['name']}` {attr['data_type']}"
                    if attr['is_primary_key']:
                        details += " (PRIMARY KEY)"
                    if attr['is_foreign_key']:
                        details += f" (FOREIGN KEY -> `{attr['references']}`)"
                    if attr['is_multivalued']:
                        details += " (Multivalorado)"
                    if attr['is_derived']:
                        details += " (Derivado)"
                    logical_model += details + "\n"
                logical_model += "\n"
            for rel in st.session_state.relationships:
                if rel["relationship_type"] == "1:N":
                    logical_model += f"- Chave estrangeira `{rel['entity1']}_id` em `{rel['entity2']}` referenciando `{rel['entity1']}`\n"
                elif rel["relationship_type"] == "N:N":
                    logical_model += f"- Tabela associativa `{rel['entity1']}_{rel['entity2']}` com FKs para `{rel['entity1']}` e `{rel['entity2']}`\n"
            st.markdown(logical_model)
            st.session_state.logical_model = logical_model  # Armazenar o modelo lógico no session_state
    else:
        # Se o diagrama já foi gerado, exibi-lo
        if 'diagram_image' in st.session_state:
            st.subheader("Diagrama ER")
            st.image(st.session_state.diagram_image)
            st.subheader("Modelo Lógico")
            st.markdown(st.session_state.logical_model)
        else:
            st.info("Clique em 'Gerar Diagrama e Modelo Lógico' para visualizar o diagrama.")

with col2:
    if 'plantuml_code' in st.session_state:
        # Botão para baixar o código PlantUML
        st.download_button(
            label="🔽 Baixar Diagrama (PlantUML)",
            data=st.session_state.plantuml_code,
            file_name="diagrama_er.puml",
            mime="text/plain"
        )
    else:
        st.info("Clique em 'Gerar Diagrama e Modelo Lógico' para visualizar e baixar o diagrama.")

    if st.button("Gerar SQL"):
        if not st.session_state.entities:
            st.error("Adicione pelo menos uma entidade para gerar o SQL.")
        else:
            sql_script = generate_sql(st.session_state.entities, st.session_state.relationships)
            st.session_state.sql_script = sql_script
            st.subheader("Script SQL")
            st.code(sql_script, language='sql')
            st.download_button(
                label="🔽 Baixar SQL",
                data=sql_script,
                file_name="modelagem.sql",
                mime="text/plain"
            )
    else:
        # Se o SQL já foi gerado, exibi-lo
        if 'sql_script' in st.session_state:
            st.subheader("Script SQL")
            st.code(st.session_state.sql_script, language='sql')