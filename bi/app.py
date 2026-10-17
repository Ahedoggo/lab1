import streamlit as st
import pandas as pd
import trino


st.set_page_config(page_title="Q10 Lakehouse", layout="wide")
st.title("Lakehouse · Возвращённые товары")
st.caption("Вариант Q10 · TPC-H Returned Item Reporting · sf1")


def query(sql):
    """Выполняет SQL-запрос в Trino и возвращает DataFrame."""
    with trino.dbapi.connect(
        host="trino",
        port=8080,
        user="bi",
        catalog="lakehouse",
    ) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)

        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]

        return pd.DataFrame(rows, columns=columns)


layer = st.radio(
    "Слой данных",
    ["Bronze", "Gold"],
    horizontal=True,
)


try:
    if layer == "Bronze":
        st.subheader("Исходные данные Bronze")

        table = st.selectbox(
            "Таблица",
            ["customer", "orders", "lineitem", "nation"],
        )

        preview_sql = f"""
            SELECT *
            FROM lakehouse.bronze.{table}
            LIMIT 100
        """

        st.code(preview_sql.strip(), language="sql")

        preview_df = query(preview_sql)

        st.dataframe(
            preview_df,
            use_container_width=True,
            hide_index=True,
        )

        revenue_sql = """
            SELECT
                n.name AS nation,
                sum(
                    l.extendedprice * (1 - l.discount)
                ) AS revenue
            FROM lakehouse.bronze.customer c
            JOIN lakehouse.bronze.nation n
                ON c.nationkey = n.nationkey
            JOIN lakehouse.bronze.orders o
                ON o.custkey = c.custkey
            JOIN lakehouse.bronze.lineitem l
                ON l.orderkey = o.orderkey
            WHERE o.orderdate >= DATE '1993-10-01'
              AND o.orderdate < DATE '1994-01-01'
              AND l.returnflag = 'R'
            GROUP BY n.name
            ORDER BY revenue DESC
        """

        st.subheader(
            "Выручка возвращённых позиций по странам — из Bronze"
        )

        st.code(revenue_sql.strip(), language="sql")

        revenue_df = query(revenue_sql)

        if revenue_df.empty:
            st.warning("Запрос не вернул данных.")
        else:
            # Trino может вернуть DECIMAL как объект Python Decimal.
            # Преобразование необходимо для построения графика.
            revenue_df["revenue"] = pd.to_numeric(
                revenue_df["revenue"],
                errors="coerce",
            )

            st.bar_chart(
                revenue_df.set_index("nation")["revenue"]
            )

            st.dataframe(
                revenue_df,
                use_container_width=True,
                hide_index=True,
            )

    else:
        st.subheader("Топ-20 клиентов · Gold")

        gold_sql = """
            SELECT *
            FROM lakehouse.gold.returned_customers_top20
            ORDER BY revenue DESC, custkey
        """

        st.code(gold_sql.strip(), language="sql")

        gold_df = query(gold_sql)

        if gold_df.empty:
            st.warning("Gold-витрина не содержит данных.")
        else:
            gold_df["revenue"] = pd.to_numeric(
                gold_df["revenue"],
                errors="coerce",
            )

            st.dataframe(
                gold_df,
                use_container_width=True,
                hide_index=True,
            )

            st.bar_chart(
                gold_df.set_index("name")["revenue"]
            )

except Exception as exc:
    st.error(
        "Данные ещё не готовы, структура таблиц не совпадает "
        "с приложением или Trino недоступен."
    )
    st.exception(exc)