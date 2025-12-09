"""HubSpot CRM client."""

import httpx
from typing import Optional, Dict, Any, List
from app.config import settings


class HubSpotClient:
    """Client for interacting with HubSpot API."""
    
    def __init__(self):
        self.api_key = settings.hubspot_api_key
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def get_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get contact information by email.
        
        Args:
            email: Contact email address
        
        Returns:
            Contact data dictionary or None if not found
        """
        url = f"{self.base_url}/crm/v3/objects/contacts"
        params = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email
                        }
                    ]
                }
            ],
            "properties": [
                "firstname", "lastname", "email", "company", "phone",
                "hubspot_owner_id", "lifecyclestage", "deal_amount"
            ]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("results") and len(data["results"]) > 0:
                    return data["results"][0]
                return None
            except httpx.HTTPError as e:
                raise Exception(f"Error fetching contact from HubSpot: {str(e)}")
    
    async def get_contact_by_id(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """
        Get contact information by HubSpot ID.
        
        Args:
            contact_id: HubSpot contact ID
        
        Returns:
            Contact data dictionary or None if not found
        """
        url = f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
        params = {
            "properties": [
                "firstname", "lastname", "email", "company", "phone",
                "hubspot_owner_id", "lifecyclestage", "deal_amount"
            ]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                raise Exception(f"Error fetching contact from HubSpot: {str(e)}")
    
    async def get_deals_for_contact(self, contact_id: str) -> List[Dict[str, Any]]:
        """
        Get deals associated with a contact.
        
        Args:
            contact_id: HubSpot contact ID
        
        Returns:
            List of deal dictionaries
        """
        url = f"{self.base_url}/crm/v4/objects/contacts/{contact_id}/associations/deals"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                deal_ids = [result["id"] for result in data.get("results", [])]
                
                if not deal_ids:
                    return []
                
                # Fetch deal details
                deals = []
                for deal_id in deal_ids:
                    deal_url = f"{self.base_url}/crm/v3/objects/deals/{deal_id}"
                    deal_params = {
                        "properties": [
                            "dealname", "amount", "dealstage", "closedate", "pipeline"
                        ]
                    }
                    deal_response = await client.get(deal_url, headers=self.headers, params=deal_params)
                    if deal_response.status_code == 200:
                        deals.append(deal_response.json())
                
                return deals
            except httpx.HTTPError as e:
                raise Exception(f"Error fetching deals from HubSpot: {str(e)}")
    
    async def search_contacts(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for contacts by name or company.
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of contact dictionaries
        """
        url = f"{self.base_url}/crm/v3/objects/contacts/search"
        payload = {
            "query": query,
            "limit": limit,
            "properties": [
                "firstname", "lastname", "email", "company"
            ]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("results", [])
            except httpx.HTTPError as e:
                raise Exception(f"Error searching contacts in HubSpot: {str(e)}")


# Simple function wrappers - no business logic, just API calls
async def get_hubspot_contact_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get HubSpot contact by email.
    
    Args:
        email: Contact email address
    
    Returns:
        Contact dictionary or None
    """
    client = HubSpotClient()
    return await client.get_contact_by_email(email)


async def get_hubspot_contact_by_id(contact_id: str) -> Optional[Dict[str, Any]]:
    """
    Get HubSpot contact by ID.
    
    Args:
        contact_id: HubSpot contact ID
    
    Returns:
        Contact dictionary or None
    """
    client = HubSpotClient()
    return await client.get_contact_by_id(contact_id)


async def get_hubspot_deals_for_contact(contact_id: str) -> List[Dict[str, Any]]:
    """
    Get deals for a HubSpot contact.
    
    Args:
        contact_id: HubSpot contact ID
    
    Returns:
        List of deal dictionaries
    """
    client = HubSpotClient()
    return await client.get_deals_for_contact(contact_id)


async def search_hubspot_contacts(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for HubSpot contacts.
    
    Args:
        query: Search query
        limit: Maximum number of results
    
    Returns:
        List of contact dictionaries
    """
    client = HubSpotClient()
    return await client.search_contacts(query, limit)

