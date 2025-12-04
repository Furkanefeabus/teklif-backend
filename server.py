from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, timedelta
from supabase import create_client, Client
import os
import bcrypt
import jwt
import io
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Table, TableStyle
import base64

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Supabase bağlantısı
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# JWT Settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

app = FastAPI(title="Invoice & Quotation API with Supabase")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# PYDANTIC MODELS
# ============================================================

class User(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    full_name: str
    company: Optional[str] = None
    phone: Optional[str] = None
    subscription_plan: str = "free"
    subscription_status: str = "active"
    subscription_end_date: Optional[datetime] = None
    company_logo: Optional[str] = None
    company_address: Optional[str] = None
    company_tax_number: Optional[str] = None
    company_tax_office: Optional[str] = None
    default_tax_rate: int = 20
    design_settings: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserSettingsUpdate(BaseModel):
    full_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    company_logo: Optional[str] = None
    company_address: Optional[str] = None
    company_tax_number: Optional[str] = None
    company_tax_office: Optional[str] = None
    default_tax_rate: Optional[int] = None
    design_settings: Optional[dict] = None

class Customer(BaseModel):
    id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    tax_number: Optional[str] = None
    tax_office: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    tax_number: Optional[str] = None
    tax_office: Optional[str] = None
    notes: Optional[str] = None

class Product(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    price: float
    stock: int = 0
    unit: str = "adet"
    sku: Optional[str] = None
    specifications: Optional[str] = None
    image_base64: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    price: float
    stock: int = 0
    unit: str = "adet"
    sku: Optional[str] = None
    specifications: Optional[str] = None
    image_base64: Optional[str] = None

class QuotationItem(BaseModel):
    product_name: str
    specifications: Optional[str] = None
    quantity: int
    unit: str = "adet"
    unit_price: float
    total: float

class Quotation(BaseModel):
    id: Optional[str] = None
    customer_id: str
    quotation_number: Optional[str] = None
    subtotal: float
    discount_amount: float = 0
    tax_rate: int = 20
    tax_amount: float
    total: float
    notes: Optional[str] = None
    status: str = "pending"
    payment_status: str = "unpaid"
    payment_date: Optional[datetime] = None
    payment_amount: Optional[float] = None
    payment_notes: Optional[str] = None
    items: List[QuotationItem] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QuotationCreate(BaseModel):
    customer_id: str
    items: List[QuotationItem]
    discount_amount: float = 0
    tax_rate: int = 20
    notes: Optional[str] = None

class Reminder(BaseModel):
    id: Optional[str] = None
    quotation_id: str
    reminder_date: datetime
    message: str
    sent: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ReminderCreate(BaseModel):
    quotation_id: str
    reminder_date: datetime
    message: str

class PaymentUpdate(BaseModel):
    payment_status: str
    payment_date: Optional[datetime] = None
    payment_amount: Optional[float] = None
    payment_notes: Optional[str] = None

class CatalogCategories(BaseModel):
    categories: List[str]

# ============================================================
# AUTH HELPERS
# ============================================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    # Kullanıcıyı Supabase'den çek
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    if not response.data:
        raise HTTPException(status_code=401, detail="User not found")
    
    return response.data[0]

# ============================================================
# AUTH ENDPOINTS
# ============================================================

@api_router.post("/auth/register")
async def register(user: UserCreate):
    # Email kontrolü
    existing = supabase.table("users").select("id").eq("email", user.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Yeni kullanıcı oluştur
    hashed_pw = hash_password(user.password)
    new_user = {
        "email": user.email,
        "password_hash": hashed_pw,
        "full_name": user.full_name,
        "subscription_plan": "free",
        "subscription_status": "active",
        "default_tax_rate": 20
    }
    
    response = supabase.table("users").insert(new_user).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    user_data = response.data[0]
    token = create_access_token({"user_id": user_data["id"]})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_data["id"],
            "email": user_data["email"],
            "full_name": user_data["full_name"]
        }
    }

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    # Kullanıcıyı bul
    response = supabase.table("users").select("*").eq("email", credentials.email).execute()
    if not response.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user = response.data[0]
    
    # Şifre kontrolü
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token({"user_id": user["id"]})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"]
        }
    }

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    return User(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        company=current_user.get("company"),
        phone=current_user.get("phone"),
        subscription_plan=current_user.get("subscription_plan", "free"),
        subscription_status=current_user.get("subscription_status", "active"),
        company_logo=current_user.get("company_logo"),
        company_address=current_user.get("company_address"),
        company_tax_number=current_user.get("company_tax_number"),
        company_tax_office=current_user.get("company_tax_office"),
        default_tax_rate=current_user.get("default_tax_rate", 20),
        design_settings=current_user.get("design_settings"),
        created_at=current_user["created_at"]
    )

@api_router.put("/auth/settings", response_model=User)
async def update_settings(settings: UserSettingsUpdate, current_user: dict = Depends(get_current_user)):
    update_data = {}
    
    if settings.full_name is not None:
        update_data["full_name"] = settings.full_name
    if settings.company is not None:
        update_data["company"] = settings.company
    if settings.phone is not None:
        update_data["phone"] = settings.phone
    if settings.company_logo is not None:
        update_data["company_logo"] = settings.company_logo
    if settings.company_address is not None:
        update_data["company_address"] = settings.company_address
    if settings.company_tax_number is not None:
        update_data["company_tax_number"] = settings.company_tax_number
    if settings.company_tax_office is not None:
        update_data["company_tax_office"] = settings.company_tax_office
    if settings.default_tax_rate is not None:
        update_data["default_tax_rate"] = settings.default_tax_rate
    if settings.design_settings is not None:
        update_data["design_settings"] = settings.design_settings
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    response = supabase.table("users").update(update_data).eq("id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to update settings")
    
    updated_user = response.data[0]
    return User(
        id=updated_user["id"],
        email=updated_user["email"],
        full_name=updated_user["full_name"],
        company=updated_user.get("company"),
        phone=updated_user.get("phone"),
        subscription_plan=updated_user.get("subscription_plan", "free"),
        subscription_status=updated_user.get("subscription_status", "active"),
        company_logo=updated_user.get("company_logo"),
        company_address=updated_user.get("company_address"),
        company_tax_number=updated_user.get("company_tax_number"),
        company_tax_office=updated_user.get("company_tax_office"),
        default_tax_rate=updated_user.get("default_tax_rate", 20),
        design_settings=updated_user.get("design_settings"),
        created_at=updated_user["created_at"]
    )

# ============================================================
# CUSTOMER ENDPOINTS
# ============================================================

@api_router.get("/customers")
async def get_customers(current_user: dict = Depends(get_current_user)):
    response = supabase.table("customers").select("*").eq("user_id", current_user["id"]).execute()
    return response.data

@api_router.post("/customers")
async def create_customer(customer: CustomerCreate, current_user: dict = Depends(get_current_user)):
    new_customer = {
        "user_id": current_user["id"],
        **customer.dict()
    }
    response = supabase.table("customers").insert(new_customer).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create customer")
    return response.data[0]

@api_router.get("/customers/{customer_id}")
async def get_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    response = supabase.table("customers").select("*").eq("id", customer_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Customer not found")
    return response.data[0]

@api_router.put("/customers/{customer_id}")
async def update_customer(customer_id: str, customer: CustomerCreate, current_user: dict = Depends(get_current_user)):
    response = supabase.table("customers").update(customer.dict(exclude_unset=True)).eq("id", customer_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Customer not found")
    return response.data[0]

@api_router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    response = supabase.table("customers").delete().eq("id", customer_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"message": "Customer deleted successfully"}

# ============================================================
# PRODUCT ENDPOINTS
# ============================================================

@api_router.get("/products")
async def get_products(current_user: dict = Depends(get_current_user)):
    response = supabase.table("products").select("*").eq("user_id", current_user["id"]).execute()
    return response.data

@api_router.post("/products")
async def create_product(product: ProductCreate, current_user: dict = Depends(get_current_user)):
    new_product = {
        "user_id": current_user["id"],
        **product.dict()
    }
    response = supabase.table("products").insert(new_product).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create product")
    return response.data[0]

@api_router.get("/products/{product_id}")
async def get_product(product_id: str, current_user: dict = Depends(get_current_user)):
    response = supabase.table("products").select("*").eq("id", product_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Product not found")
    return response.data[0]

@api_router.put("/products/{product_id}")
async def update_product(product_id: str, product: ProductCreate, current_user: dict = Depends(get_current_user)):
    response = supabase.table("products").update(product.dict(exclude_unset=True)).eq("id", product_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Product not found")
    return response.data[0]

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str, current_user: dict = Depends(get_current_user)):
    response = supabase.table("products").delete().eq("id", product_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}

# ============================================================
# QUOTATION ENDPOINTS
# ============================================================

def generate_quotation_number() -> str:
    from datetime import datetime
    import random
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_num = random.randint(1000, 9999)
    return f"Q-{timestamp}-{random_num}"

@api_router.get("/quotations")
async def get_quotations(current_user: dict = Depends(get_current_user)):
    # Quotations with customer data
    response = supabase.table("quotations").select("*, customers(*)").eq("user_id", current_user["id"]).order("created_at", desc=True).execute()
    
    quotations = []
    for quot in response.data:
        # Items çek
        items_response = supabase.table("quotation_items").select("*").eq("quotation_id", quot["id"]).execute()
        quot["items"] = items_response.data
        quot["customer"] = quot.pop("customers", {})
        quotations.append(quot)
    
    return quotations

@api_router.post("/quotations")
async def create_quotation(quotation: QuotationCreate, current_user: dict = Depends(get_current_user)):
    # Hesaplamalar
    subtotal = sum(item.total for item in quotation.items)
    taxable_amount = subtotal - quotation.discount_amount
    tax_amount = taxable_amount * (quotation.tax_rate / 100)
    total = taxable_amount + tax_amount
    
    # Quotation oluştur
    new_quotation = {
        "user_id": current_user["id"],
        "customer_id": quotation.customer_id,
        "quotation_number": generate_quotation_number(),
        "subtotal": subtotal,
        "discount_amount": quotation.discount_amount,
        "tax_rate": quotation.tax_rate,
        "tax_amount": tax_amount,
        "total": total,
        "notes": quotation.notes,
        "status": "pending",
        "payment_status": "unpaid"
    }
    
    quot_response = supabase.table("quotations").insert(new_quotation).execute()
    if not quot_response.data:
        raise HTTPException(status_code=500, detail="Failed to create quotation")
    
    quotation_id = quot_response.data[0]["id"]
    
    # Items ekle
    items_data = []
    for item in quotation.items:
        items_data.append({
            "quotation_id": quotation_id,
            **item.dict()
        })
    
    supabase.table("quotation_items").insert(items_data).execute()
    
    # Customer bilgisiyle birlikte dön
    final_response = supabase.table("quotations").select("*, customers(*)").eq("id", quotation_id).execute()
    result = final_response.data[0]
    items_response = supabase.table("quotation_items").select("*").eq("quotation_id", quotation_id).execute()
    result["items"] = items_response.data
    result["customer"] = result.pop("customers", {})
    
    return result

@api_router.get("/quotations/{quotation_id}")
async def get_quotation(quotation_id: str, current_user: dict = Depends(get_current_user)):
    response = supabase.table("quotations").select("*, customers(*)").eq("id", quotation_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    quotation = response.data[0]
    items_response = supabase.table("quotation_items").select("*").eq("quotation_id", quotation_id).execute()
    quotation["items"] = items_response.data
    quotation["customer"] = quotation.pop("customers", {})
    
    return quotation

@api_router.put("/quotations/{quotation_id}")
async def update_quotation(quotation_id: str, quotation: QuotationCreate, current_user: dict = Depends(get_current_user)):
    # Hesaplamalar
    subtotal = sum(item.total for item in quotation.items)
    taxable_amount = subtotal - quotation.discount_amount
    tax_amount = taxable_amount * (quotation.tax_rate / 100)
    total = taxable_amount + tax_amount
    
    update_data = {
        "customer_id": quotation.customer_id,
        "subtotal": subtotal,
        "discount_amount": quotation.discount_amount,
        "tax_rate": quotation.tax_rate,
        "tax_amount": tax_amount,
        "total": total,
        "notes": quotation.notes
    }
    
    response = supabase.table("quotations").update(update_data).eq("id", quotation_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    # Eski itemları sil
    supabase.table("quotation_items").delete().eq("quotation_id", quotation_id).execute()
    
    # Yeni itemları ekle
    items_data = []
    for item in quotation.items:
        items_data.append({
            "quotation_id": quotation_id,
            **item.dict()
        })
    
    supabase.table("quotation_items").insert(items_data).execute()
    
    # Güncel veriyi dön
    final_response = supabase.table("quotations").select("*, customers(*)").eq("id", quotation_id).execute()
    result = final_response.data[0]
    items_response = supabase.table("quotation_items").select("*").eq("quotation_id", quotation_id).execute()
    result["items"] = items_response.data
    result["customer"] = result.pop("customers", {})
    
    return result

@api_router.delete("/quotations/{quotation_id}")
async def delete_quotation(quotation_id: str, current_user: dict = Depends(get_current_user)):
    response = supabase.table("quotations").delete().eq("id", quotation_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return {"message": "Quotation deleted successfully"}

@api_router.put("/quotations/{quotation_id}/payment")
async def update_payment_status(quotation_id: str, payment: PaymentUpdate, current_user: dict = Depends(get_current_user)):
    update_data = payment.dict(exclude_unset=True)
    response = supabase.table("quotations").update(update_data).eq("id", quotation_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return response.data[0]

# ============================================================
# PDF GENERATION
# ============================================================

@api_router.get("/quotations/{quotation_id}/pdf")
async def generate_quotation_pdf(quotation_id: str, current_user: dict = Depends(get_current_user)):
    # Quotation verilerini çek
    response = supabase.table("quotations").select("*, customers(*)").eq("id", quotation_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    quotation = response.data[0]
    items_response = supabase.table("quotation_items").select("*").eq("quotation_id", quotation_id).execute()
    quotation["items"] = items_response.data
    customer = quotation.get("customers", {})
    
    # PDF oluştur
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Başlık
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(50, height - 50, "FİYAT TEKLİFİ")
    
    # Teklif Numarası ve Tarih
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, height - 80, f"Teklif No: {quotation.get('quotation_number', 'N/A')}")
    pdf.drawString(50, height - 95, f"Tarih: {quotation.get('created_at', '')[:10]}")
    
    # Firma Bilgileri (sol)
    y = height - 130
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Firma Bilgileri:")
    pdf.setFont("Helvetica", 10)
    y -= 20
    if current_user.get("company"):
        pdf.drawString(50, y, current_user["company"])
        y -= 15
    if current_user.get("company_address"):
        pdf.drawString(50, y, current_user["company_address"])
        y -= 15
    if current_user.get("phone"):
        pdf.drawString(50, y, f"Tel: {current_user['phone']}")
        y -= 15
    
    # Müşteri Bilgileri (sağ)
    y = height - 130
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(width - 50, y, "Müşteri Bilgileri:")
    pdf.setFont("Helvetica", 10)
    y -= 20
    if customer.get("name"):
        pdf.drawRightString(width - 50, y, customer["name"])
        y -= 15
    if customer.get("company"):
        pdf.drawRightString(width - 50, y, customer["company"])
        y -= 15
    if customer.get("address"):
        pdf.drawRightString(width - 50, y, customer["address"])
        y -= 15
    if customer.get("phone"):
        pdf.drawRightString(width - 50, y, f"Tel: {customer['phone']}")
    
    # Tablo - Ürünler
    y = height - 280
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "Ürün/Hizmet")
    pdf.drawString(250, y, "Miktar")
    pdf.drawString(320, y, "Birim")
    pdf.drawString(380, y, "Birim Fiyat")
    pdf.drawRightString(width - 50, y, "Toplam")
    
    pdf.line(50, y - 5, width - 50, y - 5)
    y -= 20
    
    pdf.setFont("Helvetica", 9)
    for item in quotation["items"]:
        pdf.drawString(50, y, item["product_name"][:40])
        pdf.drawString(250, y, str(item["quantity"]))
        pdf.drawString(320, y, item["unit"])
        pdf.drawString(380, y, f"₺{item['unit_price']:.2f}")
        pdf.drawRightString(width - 50, y, f"₺{item['total']:.2f}")
        y -= 15
        if item.get("specifications"):
            pdf.setFont("Helvetica", 8)
            pdf.drawString(60, y, f"  {item['specifications'][:60]}")
            y -= 12
            pdf.setFont("Helvetica", 9)
    
    # Toplam hesaplamalar
    y -= 10
    pdf.line(50, y, width - 50, y)
    y -= 20
    
    pdf.setFont("Helvetica", 10)
    pdf.drawString(380, y, "Ara Toplam:")
    pdf.drawRightString(width - 50, y, f"₺{quotation['subtotal']:.2f}")
    y -= 15
    
    if quotation.get("discount_amount", 0) > 0:
        pdf.drawString(380, y, "İndirim:")
        pdf.drawRightString(width - 50, y, f"-₺{quotation['discount_amount']:.2f}")
        y -= 15
    
    pdf.drawString(380, y, f"KDV ({quotation['tax_rate']}%):")
    pdf.drawRightString(width - 50, y, f"₺{quotation['tax_amount']:.2f}")
    y -= 15
    
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(380, y, "Genel Toplam:")
    pdf.drawRightString(width - 50, y, f"₺{quotation['total']:.2f}")
    
    # Notlar
    if quotation.get("notes"):
        y -= 40
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y, "Notlar:")
        y -= 15
        pdf.setFont("Helvetica", 9)
        pdf.drawString(50, y, quotation["notes"][:100])
    
    pdf.showPage()
    pdf.save()
    
    buffer.seek(0)
    return Response(content=buffer.getvalue(), media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=teklif_{quotation.get('quotation_number', 'N/A')}.pdf"
    })

# ============================================================
# REMINDERS
# ============================================================

@api_router.get("/reminders")
async def get_reminders(current_user: dict = Depends(get_current_user)):
    response = supabase.table("reminders").select("*, quotations(quotation_number, customers(*))").eq("user_id", current_user["id"]).order("reminder_date", desc=False).execute()
    return response.data

@api_router.post("/reminders")
async def create_reminder(reminder: ReminderCreate, current_user: dict = Depends(get_current_user)):
    new_reminder = {
        "user_id": current_user["id"],
        **reminder.dict()
    }
    response = supabase.table("reminders").insert(new_reminder).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create reminder")
    return response.data[0]

@api_router.post("/reminders/{reminder_id}/send")
async def send_reminder(reminder_id: str, current_user: dict = Depends(get_current_user)):
    # Hatırlatıcıyı işaretle
    response = supabase.table("reminders").update({"sent": True}).eq("id", reminder_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    return {"message": "Reminder sent successfully"}

@api_router.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str, current_user: dict = Depends(get_current_user)):
    response = supabase.table("reminders").delete().eq("id", reminder_id).eq("user_id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"message": "Reminder deleted successfully"}

# ============================================================
# STATISTICS
# ============================================================

@api_router.get("/statistics")
async def get_statistics(current_user: dict = Depends(get_current_user)):
    # Customers count
    customers_response = supabase.table("customers").select("id", count="exact").eq("user_id", current_user["id"]).execute()
    total_customers = customers_response.count or 0
    
    # Products count
    products_response = supabase.table("products").select("id", count="exact").eq("user_id", current_user["id"]).execute()
    total_products = products_response.count or 0
    
    # Quotations
    quotations_response = supabase.table("quotations").select("*").eq("user_id", current_user["id"]).execute()
    total_quotations = len(quotations_response.data)
    
    # Revenue calculations
    total_revenue = sum(q["total"] for q in quotations_response.data if q.get("payment_status") == "paid")
    pending_payments = sum(q["total"] for q in quotations_response.data if q.get("payment_status") == "unpaid")
    
    return {
        "total_customers": total_customers,
        "total_products": total_products,
        "total_quotations": total_quotations,
        "total_revenue": total_revenue,
        "pending_payments": pending_payments
    }

# ============================================================
# PAYMENTS
# ============================================================

@api_router.get("/payments/pending")
async def get_pending_payments(current_user: dict = Depends(get_current_user)):
    response = supabase.table("quotations").select("*, customers(*)").eq("user_id", current_user["id"]).eq("payment_status", "unpaid").execute()
    quotations = []
    for quot in response.data:
        quot["customer"] = quot.pop("customers", {})
        quotations.append(quot)
    return quotations

@api_router.get("/payments/paid")
async def get_paid_payments(current_user: dict = Depends(get_current_user)):
    response = supabase.table("quotations").select("*, customers(*)").eq("user_id", current_user["id"]).eq("payment_status", "paid").execute()
    quotations = []
    for quot in response.data:
        quot["customer"] = quot.pop("customers", {})
        quotations.append(quot)
    return quotations

@api_router.get("/payments/statistics")
async def get_payment_statistics(current_user: dict = Depends(get_current_user)):
    quotations_response = supabase.table("quotations").select("*").eq("user_id", current_user["id"]).execute()
    
    total_expected = sum(q["total"] for q in quotations_response.data)
    total_received = sum(q.get("payment_amount", 0) or q["total"] for q in quotations_response.data if q.get("payment_status") == "paid")
    total_pending = sum(q["total"] for q in quotations_response.data if q.get("payment_status") == "unpaid")
    overdue_count = sum(1 for q in quotations_response.data if q.get("payment_status") == "unpaid")
    
    return {
        "total_expected": total_expected,
        "total_received": total_received,
        "total_pending": total_pending,
        "overdue_count": overdue_count
    }

# ============================================================
# CATALOG / CATEGORIES
# ============================================================

@api_router.get("/catalog/categories")
async def get_categories(current_user: dict = Depends(get_current_user)):
    # Kullanıcının ürünlerinden benzersiz kategorileri çek
    response = supabase.table("products").select("category").eq("user_id", current_user["id"]).execute()
    categories = list(set(p["category"] for p in response.data if p.get("category")))
    return {"categories": sorted(categories)}

@api_router.post("/catalog/categories")
async def create_category(category_name: str, current_user: dict = Depends(get_current_user)):
    new_category = {
        "user_id": current_user["id"],
        "name": category_name
    }
    response = supabase.table("catalog_categories").insert(new_category).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create category")
    return response.data[0]

# ============================================================
# APP SETUP
# ============================================================

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Invoice & Quotation API with Supabase is running!"}

@app.get("/health")
async def health_check():
    try:
        # Supabase bağlantı testi
        supabase.table("users").select("id").limit(1).execute()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
