SELECT
            c.custkey,
            c.name,
            sum(
                l.extendedprice * (1 - l.discount)
            ) AS revenue,
            c.acctbal,
            n.name AS nation,
            c.address,
            c.phone,
            c.comment
        FROM lakehouse.bronze_orc.customer AS c
        JOIN lakehouse.bronze_orc.orders AS o
            ON c.custkey = o.custkey
        JOIN lakehouse.bronze_orc.lineitem AS l
            ON l.orderkey = o.orderkey
        JOIN lakehouse.bronze_orc.nation AS n
            ON c.nationkey = n.nationkey
        WHERE o.orderdate >= DATE '1993-10-01'
          AND o.orderdate < DATE '1994-01-01'
          AND l.returnflag = 'R'
        GROUP BY
            c.custkey,
            c.name,
            c.acctbal,
            n.name,
            c.address,
            c.phone,
            c.comment
        ORDER BY
            revenue DESC,
            c.custkey
        LIMIT 20;
