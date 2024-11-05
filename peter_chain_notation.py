import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
from io import BytesIO
import base64

st.set_page_config(page_title="Modelagem de Dados Conceitual", layout="wide")
st.title("🗂️ Modelagem de Dados Conceitual com Notação de Peter Chen")

# Função para gerar SQL
def generate_sql(entities, relationships):
    sql_statements = []
    for entity, attrs in entities.items():
        sql = f"CREATE TABLE {entity} (\n"
        primary_key = f"    {attrs[0].strip()}_id INT PRIMARY KEY,\n"  # Assume o primeiro atributo como PK
        sql += primary_key
        for attr in attrs[1:]:
            sql += f"    {attr.strip()} VARCHAR(255),\n"
        sql = sql.rstrip(",\n") + "\n);\n"
        sql_statements.append(sql)
    
    # Adicionar relacionamentos
    for rel in relationships:
        if rel["Tipo de Relacionamento"] == "1:N":
            # Adicionar FK na tabela "N"
            fk = f"ALTER TABLE {rel['Entidade 2']} ADD COLUMN {rel['Entidade 1'].lower()}_id INT,\n"
            fk += f"    ADD FOREIGN KEY ({rel['Entidade 1'].lower()}_id) REFERENCES {rel['Entidade 1']}({entities[rel['Entidade 1']][0].strip()}_id);\n"
            sql_statements.append(fk)
        elif rel["Tipo de Relacionamento"] == "N:N":
            # Criar tabela associativa
            assoc_table = f"{rel['Entidade 1']}_{rel['Entidade 2']}"
            sql = f"CREATE TABLE {assoc_table} (\n"
            sql += f"    {rel['Entidade 1'].lower()}_id INT,\n"
            sql += f"    {rel['Entidade 2'].lower()}_id INT,\n"
            sql += f"    PRIMARY KEY ({rel['Entidade 1'].lower()}_id, {rel['Entidade 2'].lower()}_id),\n"
            sql += f"    FOREIGN KEY ({rel['Entidade 1'].lower()}_id) REFERENCES {rel['Entidade 1']}({entities[rel['Entidade 1']][0].strip()}_id),\n"
            sql += f"    FOREIGN KEY ({rel['Entidade 2'].lower()}_id) REFERENCES {rel['Entidade 2']}({entities[rel['Entidade 2']][0].strip()}_id)\n"
            sql += ");\n"
            sql_statements.append(sql)
    return "\n".join(sql_statements)

# Sessão 1: Definição das Entidades
st.header("1. Definir Entidades")
st.write("Insira as entidades principais (ex.: Cliente, Pedido) e seus atributos.")

if 'entities' not in st.session_state:
    st.session_state.entities = {}

with st.form("entity_form", clear_on_submit=True):
    entity_name = st.text_input("Nome da Entidade")
    attributes = st.text_area("Atributos (separados por vírgula)", help="Exemplo: Nome, Email, Telefone")
    submitted = st.form_submit_button("Adicionar Entidade")
    if submitted:
        if entity_name and attributes:
            if entity_name in st.session_state.entities:
                st.warning(f"A entidade '{entity_name}' já existe.")
            else:
                attrs_list = [attr.strip() for attr in attributes.split(",") if attr.strip()]
                if len(attrs_list) == 0:
                    st.error("Por favor, insira pelo menos um atributo válido.")
                else:
                    st.session_state.entities[entity_name] = attrs_list
                    st.success(f"Entidade '{entity_name}' adicionada com sucesso!")
        else:
            st.error("Por favor, preencha o nome da entidade e seus atributos.")

# Exibir entidades definidas
if st.session_state.entities:
    st.subheader("Entidades Definidas:")
    for entity, attrs in st.session_state.entities.items():
        st.markdown(f"**{entity}**: {', '.join(attrs)}")

# Sessão 2: Definir Relacionamentos
st.header("2. Definir Relacionamentos")
st.write("Escolha duas entidades e defina o tipo de relacionamento entre elas.")

if 'relationships' not in st.session_state:
    st.session_state.relationships = []

if st.session_state.entities:
    with st.form("relationship_form", clear_on_submit=True):
        entity_1 = st.selectbox("Entidade 1", list(st.session_state.entities.keys()))
        entity_2 = st.selectbox("Entidade 2", list(st.session_state.entities.keys()))
        relationship_type = st.radio("Tipo de Relacionamento", ["1:1", "1:N", "N:N"])
        relationship_name = st.text_input("Nome do Relacionamento", help="Exemplo: Realiza, Contém")
        submitted_rel = st.form_submit_button("Adicionar Relacionamento")
        if submitted_rel:
            if entity_1 and entity_2 and relationship_name:
                if entity_1 == entity_2:
                    st.error("Não é permitido relacionar uma entidade consigo mesma.")
                else:
                    # Verificar se o relacionamento já existe
                    exists = False
                    for rel in st.session_state.relationships:
                        if (rel["Entidade 1"] == entity_1 and rel["Entidade 2"] == entity_2 and rel["Nome do Relacionamento"] == relationship_name):
                            exists = True
                            break
                    if exists:
                        st.warning("Este relacionamento já foi adicionado.")
                    else:
                        st.session_state.relationships.append({
                            "Entidade 1": entity_1,
                            "Entidade 2": entity_2,
                            "Nome do Relacionamento": relationship_name,
                            "Tipo de Relacionamento": relationship_type
                        })
                        st.success(f"Relacionamento '{entity_1} - {relationship_name} - {entity_2}' adicionado com sucesso!")
            else:
                st.error("Por favor, preencha todas as informações do relacionamento.")

# Exibir relacionamentos definidos
if st.session_state.relationships:
    st.subheader("Relacionamentos Definidos:")
    for rel in st.session_state.relationships:
        st.markdown(f"**{rel['Entidade 1']}** {rel['Tipo de Relacionamento']} **{rel['Nome do Relacionamento']}** **{rel['Entidade 2']}**")

# Função para converter figura para bytes
def fig_to_bytes(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    return buf

# Sessão 3: Gerar Diagrama e SQL
st.header("3. Gerar Diagrama e SQL")

col1, col2 = st.columns(2)

with col1:
    if st.button("Gerar Diagrama"):
        if not st.session_state.entities:
            st.error("Adicione pelo menos uma entidade para gerar o diagrama.")
        else:
            G = nx.DiGraph()

            # Adicionar entidades e seus atributos
            for entity, attrs in st.session_state.entities.items():
                G.add_node(entity, shape='rectangle', label=entity, type='entity')
                for attr in attrs:
                    attr_node = f"{entity}_{attr}"
                    G.add_node(attr_node, shape='ellipse', label=attr, type='attribute')
                    G.add_edge(entity, attr_node)

            # Adicionar relacionamentos entre entidades
            for rel in st.session_state.relationships:
                relationship_node = f"{rel['Entidade 1']}_{rel['Nome do Relacionamento']}_{rel['Entidade 2']}"
                G.add_node(relationship_node, shape='diamond', label=rel['Nome do Relacionamento'], type='relationship', rel_type=rel['Tipo de Relacionamento'])
                G.add_edge(rel["Entidade 1"], relationship_node, label=rel["Tipo de Relacionamento"])
                G.add_edge(relationship_node, rel["Entidade 2"], label=rel["Tipo de Relacionamento"])

            # Layout aprimorado
            pos = nx.spring_layout(G, k=1, iterations=50)

            plt.figure(figsize=(14, 10))
            
            # Desenhar nós por tipo
            entity_nodes = [n for n, attr in G.nodes(data=True) if attr['type'] == 'entity']
            attribute_nodes = [n for n, attr in G.nodes(data=True) if attr['type'] == 'attribute']
            relationship_nodes = [n for n, attr in G.nodes(data=True) if attr['type'] == 'relationship']

            nx.draw_networkx_nodes(G, pos, nodelist=entity_nodes, node_shape='s', node_color="skyblue", node_size=3000, label="Entidade")
            nx.draw_networkx_nodes(G, pos, nodelist=attribute_nodes, node_shape='o', node_color="lightgreen", node_size=2000, label="Atributo")
            nx.draw_networkx_nodes(G, pos, nodelist=relationship_nodes, node_shape='D', node_color="salmon", node_size=2500, label="Relacionamento")

            # Desenhar arestas
            nx.draw_networkx_edges(G, pos, arrows=True, arrowstyle='->', arrowsize=20, edge_color="gray")

            # Desenhar rótulos
            labels = {node: attr['label'] for node, attr in G.nodes(data=True)}
            nx.draw_networkx_labels(G, pos, labels, font_size=10, font_family="sans-serif")

            # Rótulos das arestas
            edge_labels = {(u, v): data['label'] for u, v, data in G.edges(data=True) if 'label' in data}
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color="red", font_size=8)

            plt.legend(scatterpoints=1, fontsize=12)
            plt.axis('off')
            
            # Converter figura para bytes e armazenar no estado
            buf = fig_to_bytes(plt)
            st.session_state.diagram_bytes = buf.getvalue()
            st.image(buf, caption="Diagrama ER Gerado", use_column_width=True)

with col2:
    if 'diagram_bytes' in st.session_state:
        st.download_button(
            label="🔽 Baixar Diagrama",
            data=st.session_state.diagram_bytes,
            file_name="diagrama_er.png",
            mime="image/png"
        )
    else:
        st.info("Clique em 'Gerar Diagrama' para visualizar e baixar o diagrama.")

    if st.button("Gerar SQL"):
        if not st.session_state.entities:
            st.error("Adicione pelo menos uma entidade para gerar o SQL.")
        else:
            sql_script = generate_sql(st.session_state.entities, st.session_state.relationships)
            st.session_state.sql_script = sql_script
            st.code(sql_script, language='sql')
            st.download_button(
                label="🔽 Baixar SQL",
                data=sql_script,
                file_name="modelagem.sql",
                mime="text/plain"
            )