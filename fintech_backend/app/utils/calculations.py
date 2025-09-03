"""
Financial calculation utilities for fees, interest, portfolio metrics, and more.
"""
import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum


class TransferType(str, Enum):
    """Types of money transfers."""
    DOMESTIC = "domestic"
    INTERNATIONAL = "international"
    INSTANT = "instant"
    ACH = "ach"
    WIRE = "wire"


class FeeCalculator:
    """Calculator for various financial fees."""
    
    @staticmethod
    def calculate_transfer_fee(
        amount: Decimal, 
        transfer_type: TransferType,
        is_premium_user: bool = False
    ) -> Decimal:
        """Calculate transfer fees based on amount and type."""
        
        if is_premium_user and transfer_type in [TransferType.DOMESTIC, TransferType.ACH]:
            return Decimal("0.00")  # Free for premium users
        
        # Fee structure
        fee_structure = {
            TransferType.DOMESTIC: {
                "base_fee": Decimal("0.50"),
                "percentage": Decimal("0.001"),  # 0.1%
                "max_fee": Decimal("10.00")
            },
            TransferType.INTERNATIONAL: {
                "base_fee": Decimal("5.00"),
                "percentage": Decimal("0.015"),  # 1.5%
                "max_fee": Decimal("50.00")
            },
            TransferType.INSTANT: {
                "base_fee": Decimal("1.50"),
                "percentage": Decimal("0.0025"),  # 0.25%
                "max_fee": Decimal("15.00")
            },
            TransferType.ACH: {
                "base_fee": Decimal("0.00"),
                "percentage": Decimal("0.0005"),  # 0.05%
                "max_fee": Decimal("5.00")
            },
            TransferType.WIRE: {
                "base_fee": Decimal("15.00"),
                "percentage": Decimal("0.001"),  # 0.1%
                "max_fee": Decimal("25.00")
            }
        }
        
        fees = fee_structure.get(transfer_type, fee_structure[TransferType.DOMESTIC])
        
        # Calculate fee
        percentage_fee = amount * fees["percentage"]
        total_fee = fees["base_fee"] + percentage_fee
        
        # Cap at maximum fee
        final_fee = min(total_fee, fees["max_fee"])
        
        return final_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_currency_conversion_fee(amount: Decimal, is_premium_user: bool = False) -> Decimal:
        """Calculate currency conversion fees."""
        if is_premium_user:
            rate = Decimal("0.005")  # 0.5% for premium
        else:
            rate = Decimal("0.01")   # 1% for regular users
        
        fee = (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return fee
    
    @staticmethod
    def calculate_investment_fee(transaction_amount: Decimal, fee_type: str = "standard") -> Decimal:
        """Calculate investment transaction fees."""
        fee_rates = {
            "standard": Decimal("0.0075"),  # 0.75%
            "premium": Decimal("0.005"),    # 0.5%
            "basic": Decimal("0.01")        # 1%
        }
        
        rate = fee_rates.get(fee_type, fee_rates["standard"])
        min_fee = Decimal("1.00")
        max_fee = Decimal("20.00")
        
        fee = transaction_amount * rate
        fee = max(min_fee, min(fee, max_fee))
        
        return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class InterestCalculator:
    """Calculator for interest and savings projections."""
    
    @staticmethod
    def calculate_compound_interest(
        principal: Decimal,
        annual_rate: Decimal,
        compounds_per_year: int,
        years: Decimal
    ) -> Decimal:
        """Calculate compound interest."""
        rate_per_period = annual_rate / (100 * compounds_per_year)
        total_periods = compounds_per_year * years
        
        amount = principal * ((1 + rate_per_period) ** float(total_periods))
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_savings_projection(
        current_amount: Decimal,
        monthly_contribution: Decimal,
        annual_interest_rate: Decimal,
        months: int
    ) -> Dict[str, Decimal]:
        """Calculate savings growth projection."""
        monthly_rate = annual_interest_rate / (100 * 12)
        
        balance = current_amount
        total_contributions = Decimal("0.00")
        total_interest = Decimal("0.00")
        
        for month in range(months):
            # Add monthly contribution
            balance += monthly_contribution
            total_contributions += monthly_contribution
            
            # Calculate and add interest
            interest_earned = balance * monthly_rate
            balance += interest_earned
            total_interest += interest_earned
        
        return {
            "final_balance": balance.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "total_contributions": total_contributions.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "total_interest": total_interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "initial_amount": current_amount
        }
    
    @staticmethod
    def calculate_goal_monthly_contribution(
        current_amount: Decimal,
        target_amount: Decimal,
        months_remaining: int,
        annual_interest_rate: Decimal = Decimal("0.00")
    ) -> Decimal:
        """Calculate required monthly contribution to reach a savings goal."""
        if months_remaining <= 0:
            return target_amount - current_amount
        
        if annual_interest_rate == 0:
            # Simple case without interest
            needed_amount = target_amount - current_amount
            monthly_contribution = needed_amount / months_remaining
        else:
            # With compound interest
            monthly_rate = annual_interest_rate / (100 * 12)
            
            # Future value of current amount
            future_value_current = current_amount * ((1 + monthly_rate) ** months_remaining)
            
            # Amount still needed
            amount_needed = target_amount - future_value_current
            
            if amount_needed <= 0:
                return Decimal("0.00")
            
            # Monthly payment needed (future value of annuity formula)
            if monthly_rate > 0:
                monthly_contribution = amount_needed / (
                    ((1 + monthly_rate) ** months_remaining - 1) / monthly_rate
                )
            else:
                monthly_contribution = amount_needed / months_remaining
        
        return max(Decimal("0.00"), monthly_contribution.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class PortfolioCalculator:
    """Calculator for investment portfolio metrics."""
    
    @staticmethod
    def calculate_portfolio_performance(holdings: List[Dict]) -> Dict[str, Decimal]:
        """Calculate portfolio performance metrics."""
        total_market_value = Decimal("0.00")
        total_cost_basis = Decimal("0.00")
        total_gain_loss = Decimal("0.00")
        
        for holding in holdings:
            shares = Decimal(str(holding.get("shares", 0)))
            current_price = Decimal(str(holding.get("current_price", 0)))
            avg_purchase_price = Decimal(str(holding.get("avg_purchase_price", 0)))
            
            market_value = shares * current_price
            cost_basis = shares * avg_purchase_price
            gain_loss = market_value - cost_basis
            
            total_market_value += market_value
            total_cost_basis += cost_basis
            total_gain_loss += gain_loss
        
        # Calculate percentages
        total_return_pct = Decimal("0.00")
        if total_cost_basis > 0:
            total_return_pct = (total_gain_loss / total_cost_basis * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        
        return {
            "total_market_value": total_market_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "total_cost_basis": total_cost_basis.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "total_gain_loss": total_gain_loss.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "total_return_percentage": total_return_pct,
            "number_of_holdings": len(holdings)
        }
    
    @staticmethod
    def calculate_asset_allocation(holdings: List[Dict]) -> List[Dict[str, any]]:
        """Calculate portfolio asset allocation by sector/category."""
        # Mock sector allocation (in real system, this would come from external data)
        sector_map = {
            "AAPL": "Technology",
            "GOOGL": "Technology", 
            "MSFT": "Technology",
            "TSLA": "Automotive",
            "AMZN": "E-commerce",
            "JPM": "Financial",
            "JNJ": "Healthcare",
            "PG": "Consumer Goods",
        }
        
        sector_values = {}
        total_value = Decimal("0.00")
        
        for holding in holdings:
            symbol = holding.get("symbol", "")
            shares = Decimal(str(holding.get("shares", 0)))
            current_price = Decimal(str(holding.get("current_price", 0)))
            market_value = shares * current_price
            
            sector = sector_map.get(symbol, "Other")
            sector_values[sector] = sector_values.get(sector, Decimal("0.00")) + market_value
            total_value += market_value
        
        # Calculate percentages
        allocation = []
        for sector, value in sector_values.items():
            percentage = Decimal("0.00")
            if total_value > 0:
                percentage = (value / total_value * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            allocation.append({
                "sector": sector,
                "value": value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "percentage": percentage
            })
        
        return sorted(allocation, key=lambda x: x["percentage"], reverse=True)


class RiskCalculator:
    """Calculator for financial risk metrics."""
    
    @staticmethod
    def calculate_spending_velocity(transactions: List[Dict], days: int = 30) -> Dict[str, Decimal]:
        """Calculate spending velocity and trends."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_spending = Decimal("0.00")
        transaction_count = 0
        daily_amounts = {}
        
        for transaction in transactions:
            tx_date = transaction.get("transaction_date")
            if isinstance(tx_date, str):
                tx_date = datetime.fromisoformat(tx_date.replace('Z', '+00:00'))
            
            if tx_date and tx_date >= cutoff_date:
                if transaction.get("transaction_type") == "debit":
                    amount = Decimal(str(transaction.get("amount", 0)))
                    recent_spending += amount
                    transaction_count += 1
                    
                    date_key = tx_date.date()
                    daily_amounts[date_key] = daily_amounts.get(date_key, Decimal("0.00")) + amount
        
        # Calculate metrics
        avg_daily_spending = recent_spending / days if days > 0 else Decimal("0.00")
        avg_transaction_amount = recent_spending / transaction_count if transaction_count > 0 else Decimal("0.00")
        
        # Calculate spending variance (simplified)
        daily_values = list(daily_amounts.values())
        if len(daily_values) > 1:
            mean = sum(daily_values) / len(daily_values)
            variance = sum((x - mean) ** 2 for x in daily_values) / len(daily_values)
            std_deviation = Decimal(str(math.sqrt(float(variance))))
        else:
            std_deviation = Decimal("0.00")
        
        return {
            "total_spending": recent_spending.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "avg_daily_spending": avg_daily_spending.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "avg_transaction_amount": avg_transaction_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "transaction_count": transaction_count,
            "spending_volatility": std_deviation.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "days_analyzed": days
        }
    
    @staticmethod
    def assess_spending_risk(
        monthly_income: Decimal,
        monthly_spending: Decimal,
        savings_balance: Decimal
    ) -> Dict[str, any]:
        """Assess financial risk based on spending patterns."""
        
        # Calculate metrics
        spending_ratio = monthly_spending / monthly_income if monthly_income > 0 else Decimal("999.00")
        emergency_months = savings_balance / monthly_spending if monthly_spending > 0 else Decimal("999.00")
        
        # Risk assessment
        risk_level = "low"
        risk_factors = []
        
        if spending_ratio > Decimal("0.8"):  # Spending > 80% of income
            risk_level = "high"
            risk_factors.append("High spending ratio")
        elif spending_ratio > Decimal("0.6"):  # Spending > 60% of income
            risk_level = "medium"
            risk_factors.append("Moderate spending ratio")
        
        if emergency_months < 3:
            if risk_level == "low":
                risk_level = "medium"
            risk_factors.append("Insufficient emergency fund")
        
        if emergency_months < 1:
            risk_level = "high"
            risk_factors.append("Critical emergency fund shortage")
        
        return {
            "risk_level": risk_level,
            "spending_ratio": spending_ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "emergency_fund_months": emergency_months.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
            "risk_factors": risk_factors,
            "recommendations": RiskCalculator._get_risk_recommendations(risk_level, risk_factors)
        }
    
    @staticmethod
    def _get_risk_recommendations(risk_level: str, risk_factors: List[str]) -> List[str]:
        """Get recommendations based on risk assessment."""
        recommendations = []
        
        if "High spending ratio" in risk_factors:
            recommendations.append("Consider reducing discretionary spending")
            recommendations.append("Review and categorize expenses to identify savings opportunities")
        
        if "Insufficient emergency fund" in risk_factors:
            recommendations.append("Build emergency fund to cover 3-6 months of expenses")
            recommendations.append("Set up automatic savings transfers")
        
        if "Critical emergency fund shortage" in risk_factors:
            recommendations.append("Prioritize building emergency fund immediately")
            recommendations.append("Consider reducing non-essential expenses")
        
        if risk_level == "low":
            recommendations.append("Consider increasing investment contributions")
            recommendations.append("Explore additional savings goals")
        
        return recommendations


class AnalyticsCalculator:
    """Calculator for financial analytics and insights."""
    
    @staticmethod
    def calculate_spending_by_category(transactions: List[Dict], days: int = 30) -> List[Dict]:
        """Calculate spending breakdown by category."""
        cutoff_date = datetime.now() - timedelta(days=days)
        category_totals = {}
        
        for transaction in transactions:
            tx_date = transaction.get("transaction_date")
            if isinstance(tx_date, str):
                tx_date = datetime.fromisoformat(tx_date.replace('Z', '+00:00'))
            
            if (tx_date and tx_date >= cutoff_date and 
                transaction.get("transaction_type") == "debit"):
                
                category = transaction.get("category", "Other")
                amount = Decimal(str(transaction.get("amount", 0)))
                category_totals[category] = category_totals.get(category, Decimal("0.00")) + amount
        
        # Calculate total for percentages
        total_spending = sum(category_totals.values())
        
        # Format results
        results = []
        for category, amount in category_totals.items():
            percentage = Decimal("0.00")
            if total_spending > 0:
                percentage = (amount / total_spending * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            
            results.append({
                "category": category,
                "amount": amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "percentage": percentage,
                "transaction_count": len([t for t in transactions 
                                       if t.get("category") == category and 
                                       t.get("transaction_type") == "debit"])
            })
        
        return sorted(results, key=lambda x: x["amount"], reverse=True)
    
    @staticmethod
    def calculate_monthly_trends(transactions: List[Dict], months: int = 6) -> List[Dict]:
        """Calculate monthly spending trends."""
        monthly_data = {}
        
        for transaction in transactions:
            tx_date = transaction.get("transaction_date")
            if isinstance(tx_date, str):
                tx_date = datetime.fromisoformat(tx_date.replace('Z', '+00:00'))
            
            if tx_date and transaction.get("transaction_type") == "debit":
                month_key = tx_date.strftime("%Y-%m")
                amount = Decimal(str(transaction.get("amount", 0)))
                
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "month": month_key,
                        "total_spending": Decimal("0.00"),
                        "transaction_count": 0
                    }
                
                monthly_data[month_key]["total_spending"] += amount
                monthly_data[month_key]["transaction_count"] += 1
        
        # Sort by month and format
        trends = []
        for month_data in sorted(monthly_data.values(), key=lambda x: x["month"]):
            trends.append({
                "month": month_data["month"],
                "total_spending": month_data["total_spending"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "transaction_count": month_data["transaction_count"],
                "avg_transaction_amount": (
                    month_data["total_spending"] / month_data["transaction_count"]
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if month_data["transaction_count"] > 0 else Decimal("0.00")
            })
        
        return trends[-months:] if months else trends


class LimitCalculator:
    """Calculator for spending limits and validations."""
    
    @staticmethod
    def check_spending_limit(
        current_spent: Decimal,
        transaction_amount: Decimal,
        limit: Decimal,
        limit_type: str = "daily"
    ) -> Dict[str, any]:
        """Check if transaction would exceed spending limit."""
        projected_total = current_spent + transaction_amount
        
        return {
            "within_limit": projected_total <= limit,
            "current_spent": current_spent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "transaction_amount": transaction_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "projected_total": projected_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "limit": limit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "remaining_limit": max(Decimal("0.00"), limit - projected_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "limit_type": limit_type,
            "utilization_percentage": (projected_total / limit * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if limit > 0 else Decimal("0.0")
        }
    
    @staticmethod
    def suggest_optimal_limits(
        historical_transactions: List[Dict],
        days_to_analyze: int = 90
    ) -> Dict[str, Decimal]:
        """Suggest optimal spending limits based on historical data."""
        cutoff_date = datetime.now() - timedelta(days=days_to_analyze)
        
        daily_spending = {}
        monthly_spending = {}
        
        for transaction in historical_transactions:
            tx_date = transaction.get("transaction_date")
            if isinstance(tx_date, str):
                tx_date = datetime.fromisoformat(tx_date.replace('Z', '+00:00'))
            
            if (tx_date and tx_date >= cutoff_date and 
                transaction.get("transaction_type") == "debit"):
                
                amount = Decimal(str(transaction.get("amount", 0)))
                
                # Daily aggregation
                date_key = tx_date.date()
                daily_spending[date_key] = daily_spending.get(date_key, Decimal("0.00")) + amount
                
                # Monthly aggregation  
                month_key = tx_date.strftime("%Y-%m")
                monthly_spending[month_key] = monthly_spending.get(month_key, Decimal("0.00")) + amount
        
        # Calculate suggested limits (add 20% buffer to 90th percentile)
        daily_amounts = list(daily_spending.values())
        monthly_amounts = list(monthly_spending.values())
        
        if daily_amounts:
            daily_amounts.sort()
            daily_90th = daily_amounts[int(len(daily_amounts) * 0.9)] if daily_amounts else Decimal("100.00")
            suggested_daily = (daily_90th * Decimal("1.2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            suggested_daily = Decimal("500.00")  # Default
        
        if monthly_amounts:
            monthly_amounts.sort()
            monthly_90th = monthly_amounts[int(len(monthly_amounts) * 0.9)] if monthly_amounts else Decimal("3000.00")
            suggested_monthly = (monthly_90th * Decimal("1.2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            suggested_monthly = Decimal("15000.00")  # Default
        
        return {
            "suggested_daily_limit": suggested_daily,
            "suggested_monthly_limit": suggested_monthly,
            "analysis_period_days": days_to_analyze,
            "data_points_daily": len(daily_spending),
            "data_points_monthly": len(monthly_spending)
        }
