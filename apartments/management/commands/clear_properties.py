from django.core.management.base import BaseCommand
from apartments.models import Apartment, ApartmentImages, LeasingCompany


class Command(BaseCommand):
    help = "Clear all apartment, image, and leasing company records from the database."

    def handle(self, *args, **kwargs):
        image_count = ApartmentImages.objects.count()
        apartment_count = Apartment.objects.count()
        company_count = LeasingCompany.objects.count()

        ApartmentImages.objects.all().delete()
        Apartment.objects.all().delete()
        LeasingCompany.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(
            f"Deleted {image_count} ApartmentImages, "
            f"{apartment_count} Apartments, "
            f"{company_count} LeasingCompanies."
        ))