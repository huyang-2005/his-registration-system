"""请求模型：表单与 JSON 入参统一校验。"""
from pydantic import BaseModel, Field


class LoginModel(BaseModel):
    username: str = ""
    password: str = ""


class TriageModel(BaseModel):
    symptoms: str = ""


class PatientCreateModel(BaseModel):
    name: str = ""
    gender: str = ""
    birth_date: str = ""
    id_card: str = ""
    phone: str = ""
    address: str = ""
    patient_type: str = "自费"
    insurance_no: str = ""


class RegisterSubmitModel(BaseModel):
    schedule_id: str = ""
    patient_id: str = ""
    reg_type: str = "现场"


class RegistrationPayModel(BaseModel):
    pay_type: str = "现金"


class ScheduleCreateModel(BaseModel):
    doctor_id: str = ""
    work_date: str = ""
    time_period: str = ""
    level_id: str = ""
    total_quota: str = "0"


class RegisterApiModel(BaseModel):
    schedule_id: int
    patient_name: str = Field(default="", max_length=50)
    patient_id_card: str = Field(default="", max_length=18)
    phone: str = Field(default="", max_length=20)


class DepartmentCreateModel(BaseModel):
    dept_code: str = ""
    dept_name: str = ""
    dept_type: str = "门诊"
    location: str = ""


class DoctorCreateModel(BaseModel):
    doctor_code: str = ""
    doctor_name: str = ""
    dept_id: str = ""
    title: str = ""
    gender: str = ""


class DrugCreateModel(BaseModel):
    drug_code: str = ""
    generic_name: str = ""
    trade_name: str = ""
    spec: str = ""
    dosage_form: str = ""
    unit: str = "盒"
    price: str = "0"
    insurance_category: str = "甲类"
    manufacturer: str = ""


class InventoryCreateModel(BaseModel):
    batch_no: str = ""
    quantity: str = "0"
    expiry_date: str = ""


class PrescriptionCreateModel(BaseModel):
    reg_id: str = ""
    diagnosis: str = ""


class PrescriptionPayModel(BaseModel):
    pay_type: str = "现金"


class PrescriptionItemModel(BaseModel):
    drug_id: int
    quantity: int


class PrescriptionApiModel(BaseModel):
    reg_id: int
    diagnosis: str = ""
    items: list[PrescriptionItemModel] = []

