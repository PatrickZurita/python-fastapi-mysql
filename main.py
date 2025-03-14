from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Field, Session, create_engine, select, SQLModel, Relationship
from typing import List, Optional
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=True)

def get_session():
    with Session(engine) as session:
        yield session

class OrderProduct(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")
    product_id: int
    quantity: int
    unit_price: float

    order: Optional["Order"] = Relationship(back_populates="products")

class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_number: str = Field(unique=True, index=True)
    date: str
    final_price: float

    products: List["OrderProduct"] = Relationship(back_populates="order")

class OrderProductSchema(SQLModel):
    product_id: int
    quantity: int
    unit_price: float
    name: Optional[str] = None  

class OrderSchema(SQLModel):
    order_number: str
    date: str
    final_price: float
    products: List[OrderProductSchema]

    class Config:
        orm_mode = True

class OrderResponse(SQLModel):
    id: int
    order_number: str
    date: str
    final_price: float
    products: List[OrderProduct]

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/orders")
def get_orders(session: Session = Depends(get_session)):
    orders = session.exec(select(Order)).all()

    result = []
    for order in orders:
        products = session.exec(
            select(OrderProduct).where(OrderProduct.order_id == order.id)
        ).all()

        result.append({
            "id": order.id,
            "order_number": order.order_number,
            "date": order.date,
            "final_price": order.final_price,
            "products": [product.dict() for product in products],
        })

    return result

@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, session: Session = Depends(get_session)):
    order = session.exec(select(Order).where(Order.id == order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    products = session.exec(select(OrderProduct).where(OrderProduct.order_id == order_id)).all()

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        date=order.date,
        final_price=order.final_price,
        products=products
    )

@app.post("/orders", response_model=OrderSchema)
def create_order(order: OrderSchema, session: Session = Depends(get_session)):
    db_order = Order(
        order_number=order.order_number,
        date=order.date,
        final_price=order.final_price,
    )
    
    session.add(db_order)
    session.commit()
    session.refresh(db_order)  

    db_products = []
    for product in order.products:
        db_product = OrderProduct(
            order_id=db_order.id,
            product_id=product.product_id,
            quantity=product.quantity,
            unit_price=product.unit_price,
        )
        session.add(db_product)
        db_products.append(db_product)

    session.commit()

    return {
        "id": db_order.id,
        "order_number": db_order.order_number,
        "date": db_order.date,
        "final_price": db_order.final_price,
        "products": db_products  
    }

@app.put("/orders/{order_id}", response_model=OrderResponse)
def update_order(order_id: int, order_data: OrderSchema, session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.order_number = order_data.order_number
    order.final_price = order_data.final_price
    order.date = order_data.date

    session.query(OrderProduct).filter(OrderProduct.order_id == order_id).delete()

    db_products = []
    for product in order_data.products:
        new_product = OrderProduct(
            order_id=order_id,
            product_id=product.product_id,
            quantity=product.quantity,
            unit_price=product.unit_price
        )
        session.add(new_product)
        db_products.append(new_product)

    session.commit()
    session.refresh(order)

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        date=order.date,
        final_price=order.final_price,
        products=db_products
    )

@app.delete("/orders/{order_id}")
def delete_order(order_id: int, session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    products = session.exec(select(OrderProduct).where(OrderProduct.order_id == order_id)).all()
    for product in products:
        session.delete(product)

    session.delete(order)
    session.commit()

    return {"message": "Order deleted successfully"}

