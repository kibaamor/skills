# Domain Language

Accounts and Checkout are separate bounded contexts. In Accounts, a **hold** is an indefinite restriction that blocks account activity. In Checkout, a **hold** is an expiring payment authorization for one order.
